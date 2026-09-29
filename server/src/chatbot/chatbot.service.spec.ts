import { ChatbotService, MAIN_BUTTONS, MORE_BUTTON, MORE_BUTTONS, formatSection, isGreetingOnly, openingLine, timeGreeting, toWhatsAppFormat } from './chatbot.service';

function payload(body: string, id = 'wamid.1', from = '919876543210') {
  return {
    object: 'whatsapp_business_account',
    entry: [{
      id: 'waba',
      changes: [{
        field: 'messages',
        value: {
          messages: [{ from, id, timestamp: '1', type: 'text', text: { body } }],
        },
      }],
    }],
  };
}

function buttonPayload(id: string, title: string, messageId = 'wamid.btn', from = '919876543210') {
  return {
    object: 'whatsapp_business_account',
    entry: [{
      id: 'waba',
      changes: [{
        field: 'messages',
        value: {
          messages: [{
            from,
            id: messageId,
            timestamp: '1',
            type: 'interactive',
            interactive: { type: 'button_reply', button_reply: { id, title } },
          }],
        },
      }],
    }],
  };
}

function env(overrides: NodeJS.ProcessEnv = {}): NodeJS.ProcessEnv {
  return {
    CHATBOT_ENABLED: 'true',
    WHATSAPP_ENABLED: 'true',
    WHATSAPP_RECIPIENTS: '919876543210',
    WHATSAPP_ACCESS_TOKEN: 'test-token',
    WHATSAPP_PHONE_NUMBER_ID: '123',
    ...overrides,
  };
}

function fetchImpl(calls: string[]): typeof fetch {
  return (async (_url: string | URL | Request, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body || '{}')) as { to?: string; type?: string };
    calls.push(`${body.type}:${body.to}`);
    return { ok: true, json: async () => ({ messages: [{ id: 'out' }] }) } as Response;
  }) as typeof fetch;
}

function capture(sent: Array<Record<string, unknown>>): typeof fetch {
  return (async (_url: string | URL | Request, init?: RequestInit) => {
    sent.push(JSON.parse(String(init?.body || '{}')) as Record<string, unknown>);
    return { ok: true, json: async () => ({ messages: [{ id: 'out' }] }) } as Response;
  }) as typeof fetch;
}

const news = [
  { title: 'Older road work', summary: 'A drain was repaired.', category: 'Civic', sentiment: 'Positive', severity: 'low', place: 'Narasaraopet', source: 'lokal', url: 'https://example.com/old', publishedAt: '2026-09-01T00:00:00Z', collectedAt: '2026-09-01T00:00:00Z' },
  { title: 'Sixth item', summary: 'This must not appear.', category: 'Civic', sentiment: 'Neutral', severity: 'low', place: 'Sattenapalle', source: 'lokal', url: 'https://example.com/six', publishedAt: '2026-09-02T00:00:00Z', collectedAt: '2026-09-02T00:00:00Z' },
  { title: 'Fifth item', summary: 'Market update.', category: 'Economy', sentiment: 'Neutral', severity: 'low', place: 'Chilakaluripet', source: 'sakshi', url: 'https://example.com/five', publishedAt: '2026-09-03T00:00:00Z', collectedAt: '2026-09-03T00:00:00Z' },
  { title: 'Fourth item', summary: 'School notice.', category: 'Education', sentiment: 'Positive', severity: 'low', place: 'Narasaraopet', source: 'youtube', url: 'https://example.com/four', publishedAt: '2026-09-04T00:00:00Z', collectedAt: '2026-09-04T00:00:00Z' },
  { title: 'Third item', summary: 'Water supply.', category: 'Civic', sentiment: 'Negative', severity: 'moderate', place: 'Vinukonda', source: 'lokal', url: 'https://example.com/three', publishedAt: '2026-09-05T00:00:00Z', collectedAt: '2026-09-05T00:00:00Z' },
  { title: 'Second item', summary: 'Crop loss.', category: 'Agriculture', sentiment: 'Negative', severity: 'high', place: 'Macherla', source: 'sakshi', url: 'https://example.com/two', publishedAt: '2026-09-06T00:00:00Z', collectedAt: '2026-09-06T00:00:00Z' },
  { title: 'Cordon search in Narasaraopet', summary: 'Police searched the Pedda Cheruvu area.', category: 'Crime', sentiment: 'Negative', severity: 'high', place: 'Narasaraopet, Palnadu', source: 'youtube', url: 'https://www.youtube.com/watch?v=x', publishedAt: '2026-09-27T07:26:08Z', collectedAt: '2026-09-28T04:32:17Z' },
];

describe('ChatbotService', () => {
  it('shows the six reply buttons and ignores a second delivery of the same message', async () => {
    const calls: string[] = [];
    const bot = new ChatbotService();
    await bot.handle(payload('Who are you?'), { env: env(), fetchImpl: fetchImpl(calls) });
    await bot.handle(payload('Who are you?'), { env: env(), fetchImpl: fetchImpl(calls) });
    expect(calls).toEqual(['interactive:919876543210', 'interactive:919876543210']);
  });

  it('does not reply when the allowlist is empty or the sender is not listed', async () => {
    const calls: string[] = [];
    const bot = new ChatbotService();
    await bot.handle(payload('Hello'), { env: env({ WHATSAPP_RECIPIENTS: '' }), fetchImpl: fetchImpl(calls) });
    await bot.handle(payload('Hello', 'wamid.2', '911111111111'), { env: env(), fetchImpl: fetchImpl(calls) });
    expect(calls).toEqual([]);
  });

  it('does not reply to delivery statuses', async () => {
    const calls: string[] = [];
    const bot = new ChatbotService();
    await bot.handle({
      object: 'whatsapp_business_account',
      entry: [{ changes: [{ value: { statuses: [{ id: 'wamid.1', status: 'delivered', recipient_id: '919876543210' }] } }] }],
    }, { env: env(), fetchImpl: fetchImpl(calls) });
    expect(calls).toEqual([]);
  });

  it('answers a greeting with reply buttons, not links', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(payload('Hi', 'wamid.hi'), {
      env: env(),
      fetchImpl: capture(sent),
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    expect(sent).toHaveLength(2);
    expect(sent.every((row) => row.type === 'interactive')).toBe(true);
    const first = sent[0].interactive as { type: string; body: { text: string }; action: { buttons: Array<{ type: string; reply: { id: string; title: string } }> } };
    const second = sent[1].interactive as { body: { text: string }; action: { buttons: Array<{ reply: { title: string } }> } };
    expect(first.type).toBe('button');
    expect(first.body.text).toContain("Good evening, Sri. Lavu Sri Krishna Devarayalu Sir! I'm your Media Assistant.");
    expect(first.body.text).toContain('Tap a section');
    expect(first.action.buttons.map((button) => button.reply.title)).toEqual(['News', 'Grievances', 'Constituency']);
    expect(first.action.buttons.every((button) => button.type === 'reply')).toBe(true);
    expect(second.body.text).toBe('More');
    expect(second.action.buttons.map((button) => button.reply.title)).toEqual(['More']);
    expect(JSON.stringify(sent)).not.toContain('http');
  });

  it('returns only the latest five news items when News is tapped, then shows the menu again', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(buttonPayload('news', 'News', 'wamid.news'), {
      env: env(),
      fetchImpl: capture(sent),
      news,
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    const text = sent[0].text as { body: string };
    expect(sent[0].type).toBe('text');
    expect(text.body).toContain('*News*');
    expect(text.body).toContain('Latest 5');
    expect(text.body).toContain('Cordon search in Narasaraopet');
    expect(text.body).toContain('Second item');
    expect(text.body).not.toContain('Sixth item');
    expect(text.body).not.toContain('Older road work');
    expect(text.body).not.toContain('http');
    expect(sent.slice(1).map((row) => row.type)).toEqual(['interactive', 'interactive']);
    const titles = sent.slice(1).flatMap((row) => {
      const interactive = row.interactive as { action: { buttons: Array<{ reply: { title: string } }> } };
      return interactive.action.buttons.map((button) => button.reply.title);
    });
    expect(titles).toEqual([...MAIN_BUTTONS, MORE_BUTTON].map((button) => button.title));
  });

  it('opens Projects, Campaigns, and Analytics from More', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(buttonPayload('more', 'More', 'wamid.more'), {
      env: env(),
      fetchImpl: capture(sent),
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    expect(sent).toHaveLength(1);
    const interactive = sent[0].interactive as { body: { text: string }; action: { buttons: Array<{ reply: { id: string; title: string } }> } };
    expect(interactive.body.text).toBe('More');
    expect(interactive.action.buttons.map((button) => button.reply.title)).toEqual(MORE_BUTTONS.map((button) => button.title));
    expect(interactive.action.buttons.map((button) => button.reply.id)).toEqual(['projects', 'campaigns', 'analytics']);
  });

  it('returns the five newest grievances and keeps projects separate', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    const records = {
      grievances: [
        { title: 'Old drain', detail: 'See https://example.com/drain', status: 'Closed', date: '2026-08-01T00:00:00Z' },
        { title: 'Sixth grievance', detail: 'Too old', status: 'Open', date: '2026-08-02T00:00:00Z' },
        { title: 'Street light', detail: 'Ward 4', status: 'Open', date: '2026-09-05T00:00:00Z' },
        { title: 'Pension delay', detail: 'Two households', status: 'In progress', date: '2026-09-06T00:00:00Z' },
        { title: 'Water tanker', detail: 'Colony request', status: 'Open', date: '2026-09-07T00:00:00Z' },
        { title: 'Road patch', detail: 'Main road', status: 'Open', date: '2026-09-08T00:00:00Z' },
        { title: 'Ration card', detail: 'Missing name', status: 'Open', date: '2026-09-09T00:00:00Z' },
      ],
      projects: [{ title: 'School building', detail: 'Roof work', status: 'Open', date: '2026-09-09T00:00:00Z' }],
    };
    await bot.handle(buttonPayload('grievances', 'Grievances', 'wamid.g'), {
      env: env(),
      fetchImpl: capture(sent),
      records,
      now: () => new Date('2026-09-28T04:00:00Z'),
    });
    const body = (sent[0].text as { body: string }).body;
    expect(body).toContain('*Grievances*');
    expect(body).toContain('Ration card');
    expect(body).toContain('Street light');
    expect(body).not.toContain('Sixth grievance');
    expect(body).not.toContain('Old drain');
    expect(body).not.toContain('School building');
    expect(body).not.toContain('http');
    expect(body).not.toContain('example.com');
  });

  it('opens each conversation with the greeting, but not every reply', async () => {
    const sent: string[] = [];
    const recording = (async (_url: string | URL | Request, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body || '{}')) as { type?: string; text?: { body?: string }; interactive?: { body?: { text?: string } } };
      sent.push(body.type === 'text' ? body.text?.body || '' : body.interactive?.body?.text || '');
      return { ok: true, json: async () => ({ messages: [{ id: 'out' }] }) } as Response;
    }) as typeof fetch;
    const bot = new ChatbotService();
    let clock = new Date('2026-09-28T12:50:00Z');
    const deps = { env: env(), fetchImpl: recording, news: [], now: () => clock };
    await bot.handle(payload('latest updates', 'wamid.g1'), deps);
    clock = new Date('2026-09-28T13:00:00Z');
    await bot.handle(payload('Hello', 'wamid.g2'), deps);
    clock = new Date('2026-09-29T03:30:00Z');
    await bot.handle(payload('any news?', 'wamid.g3'), deps);
    expect(sent[0]).toContain("Good evening, Sri. Lavu Sri Krishna Devarayalu Sir! I'm your Media Assistant.");
    expect(sent[0]).toContain('*News*');
    expect(sent[3]).toBe('Tap a section. The reply stays in this chat.');
    expect(sent[5]).toContain("Good morning, Sri. Lavu Sri Krishna Devarayalu Sir! I'm your Media Assistant.");
  });

  it('greets by India time of day', () => {
    expect(timeGreeting(new Date('2026-09-28T03:30:00Z'))).toBe('Good morning');
    expect(timeGreeting(new Date('2026-09-28T08:00:00Z'))).toBe('Good afternoon');
    expect(timeGreeting(new Date('2026-09-28T12:50:00Z'))).toBe('Good evening');
    expect(timeGreeting(new Date('2026-09-28T20:00:00Z'))).toBe('Good evening');
    expect(openingLine(new Date('2026-09-28T03:30:00Z'), {}))
      .toBe("Good morning, Sri. Lavu Sri Krishna Devarayalu Sir! I'm your Media Assistant.");
  });

  it('recognises a bare greeting but not a question', () => {
    for (const text of ['Hi', 'hello sir', 'Good evening!', 'నమస్కారం', 'Namaste garu', 'hey 👋']) {
      expect(isGreetingOnly(text)).toBe(true);
    }
    for (const text of ['hi, any news from Macherla?', 'latest updates', 'good news today?', '']) {
      expect(isGreetingOnly(text)).toBe(false);
    }
  });

  it('converts markdown bold and headings to WhatsApp formatting', () => {
    expect(toWhatsAppFormat('## Today\n**Narasaraopet** – *Crime* – __theft__')).toBe('Today\n*Narasaraopet* – *Crime* – _theft_');
  });

  it('lets a failed send be tried again', async () => {
    const bot = new ChatbotService();
    const failing = (async () => ({ ok: false, json: async () => ({}) })) as typeof fetch;
    await bot.handle(payload('Hi', 'wamid.fail'), { env: env(), fetchImpl: failing });
    const calls: string[] = [];
    await bot.handle(payload('Hi', 'wamid.fail'), { env: env(), fetchImpl: fetchImpl(calls) });
    expect(calls.some((call) => call.startsWith('interactive:'))).toBe(true);
  });

  it('caps a section at five lines', () => {
    const body = formatSection('News', ['a', 'b', 'c', 'd', 'e', 'f']);
    expect(body).toContain('Latest 5');
    expect(body).not.toContain('6. f');
  });
});
