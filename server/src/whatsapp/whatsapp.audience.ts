/** Who may be answered, and who receives pipeline success and failure. Empty until contacts load. */

export type StaffRole = 'superadmin' | 'admin' | 'user';

const rank: Record<StaffRole, number> = { user: 0, admin: 1, superadmin: 2 };

let loaded = false;
let superAdmins = new Set<string>();
let staff = new Set<string>();

function digits(value: string): string {
  return String(value || '').replace(/\D/g, '');
}

export function staffRole(value: unknown): StaffRole {
  return value === 'superadmin' || value === 'admin' ? value : 'user';
}

/** The highest role wins when the same number is stored more than once. */
export function setStaffDirectory(entries: Array<{ phone: string; role: StaffRole }>): void {
  const best = new Map<string, StaffRole>();
  for (const entry of entries) {
    const phone = digits(entry.phone);
    if (!phone) continue;
    const role = staffRole(entry.role);
    const current = best.get(phone);
    if (!current || rank[role] > rank[current]) best.set(phone, role);
  }
  superAdmins = new Set([...best].filter(([, role]) => role === 'superadmin').map(([phone]) => phone));
  staff = new Set([...best].filter(([, role]) => role !== 'user').map(([phone]) => phone));
  loaded = true;
}

export function clearStaffDirectory(): void {
  loaded = false;
  superAdmins = new Set();
  staff = new Set();
}

export function staffDirectoryLoaded(): boolean {
  return loaded;
}

/** Sarojininaidu's role: pipeline success, pipeline failure, and every other alert. */
export function pipelineRecipients(): string[] {
  return [...superAdmins];
}

/** Super admin and admins. The bot answers only these numbers. */
export function replyRecipients(): string[] {
  return [...staff];
}
