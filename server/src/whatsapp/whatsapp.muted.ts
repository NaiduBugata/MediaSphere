/**
 * Numbers that only receive one-way messages (birthday wishes). Their incoming messages are dropped
 * before the webhook stores them or the chatbot sees them, even when the number is on WHATSAPP_RECIPIENTS.
 */
let muted = new Set<string>();

function digits(value: unknown): string {
  return String(value ?? '').replace(/\D/g, '');
}

export function setMutedSenders(numbers: Iterable<string>): void {
  muted = new Set([...numbers].map(digits).filter(Boolean));
}

export function isMutedSender(waId: unknown): boolean {
  return muted.has(digits(waId));
}

/**
 * Copy of a webhook payload without messages (and contact names) from muted numbers. Delivery statuses stay.
 * A change or entry left with nothing in it is removed, so nothing is stored for it.
 */
export function withoutMutedMessages(payload: unknown): { payload: unknown; dropped: number } {
  if (!muted.size || !payload || typeof payload !== 'object' || !Array.isArray((payload as Record<string, unknown>).entry)) {
    return { payload, dropped: 0 };
  }
  let dropped = 0;
  const body = payload as Record<string, unknown>;
  const entries = (body.entry as unknown[]).map((entry) => {
    if (!entry || typeof entry !== 'object' || !Array.isArray((entry as Record<string, unknown>).changes)) return entry;
    const row = entry as Record<string, unknown>;
    const changes = (row.changes as unknown[]).map((change) => {
      const value = change && typeof change === 'object' ? (change as Record<string, unknown>).value : null;
      if (!value || typeof value !== 'object' || !Array.isArray((value as Record<string, unknown>).messages)) return change;
      const original = value as Record<string, unknown>;
      const messages = (original.messages as unknown[]).filter((message) => {
        const hit = message && typeof message === 'object' && isMutedSender((message as Record<string, unknown>).from);
        if (hit) dropped += 1;
        return !hit;
      });
      if (messages.length === (original.messages as unknown[]).length) return change;
      const next: Record<string, unknown> = { ...original, messages };
      if (Array.isArray(original.contacts)) {
        next.contacts = original.contacts.filter((contact) => !(contact && typeof contact === 'object' && isMutedSender((contact as Record<string, unknown>).wa_id)));
      }
      const hasContent = messages.length > 0
        || (Array.isArray(next.statuses) && next.statuses.length > 0)
        || Boolean(next.message_template_status_update)
        || (Array.isArray(next.errors) && next.errors.length > 0);
      return hasContent ? { ...(change as Record<string, unknown>), value: next } : null;
    }).filter((change) => change !== null);
    return changes.length ? { ...row, changes } : null;
  }).filter((entry) => entry !== null);
  return { payload: dropped ? { ...body, entry: entries } : payload, dropped };
}
