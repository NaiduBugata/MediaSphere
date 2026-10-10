import { FOLLOW_UP_SENT } from '../visits/visit-followup';
import { clearStaffDirectory, setStaffDirectory } from '../whatsapp/whatsapp.audience';
import { classifyGrievance } from './grievance-priority';
import { ChatbotService, GRIEVANCE_RECEIPT, MAIN_BUTTONS, MAIN_MENU_TEXT, VISIT_BUTTONS, formatSection, isGreetingOnly, openingLine, timeGreeting, toWhatsAppFormat } from './chatbot.service';

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

function messageText(message: Record<string, unknown>): string {
  if (message.type === 'text') return String((message.text as { body?: string } | undefined)?.body || '');
  const interactive = message.interactive as { body?: { text?: string } } | undefined;
  return interactive?.body?.text || '';
}

function replyButtons(message: Record<string, unknown>): Array<{ id: string; title: string }> {
  const interactive = message.interactive as {
    type?: string;
    action?: {
      buttons?: Array<{ reply: { id: string; title: string } }>;
      sections?: Array<{ rows?: Array<{ id: string; title: string }> }>;
    };
  } | undefined;
  if (interactive?.type === 'list') return (interactive.action?.sections || []).flatMap((section) => section.rows || []);
  if (interactive?.type !== 'button') return [];
  return (interactive.action?.buttons || []).map((button) => button.reply);
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

function memoryRecords() {
  const rows: Array<Record<string, unknown>> = [];
  const matches = (row: Record<string, unknown>, filter: Record<string, unknown>) =>
    Object.entries(filter).every(([key, value]) => row[key] === value);
  const db = {
    ensureConnected: async () => true,
    collection: () => ({
      findOne: async (filter: Record<string, unknown>) => rows.find((row) => matches(row, filter)) || null,
      insertOne: async (doc: Record<string, unknown>) => {
        rows.push({ ...doc });
        return { insertedId: 'id' };
      },
      find: (filter: Record<string, unknown>) => ({
        sort: () => ({
          limit: () => ({
            toArray: async () => rows.filter((row) => matches(row, filter)),
          }),
        }),
      }),
    }),
  };
  return { rows, db };
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
  afterEach(() => clearStaffDirectory());

  it('shows the six reply buttons and ignores a second delivery of the same message', async () => {
    const calls: string[] = [];
    const bot = new ChatbotService();
    await bot.handle(payload('Who are you?'), { env: env(), fetchImpl: fetchImpl(calls) });
    await bot.handle(payload('Who are you?'), { env: env(), fetchImpl: fetchImpl(calls) });
    expect(calls).toEqual(['interactive:919876543210']);
  });

  it('does not reply when the allowlist is empty or the sender is not listed', async () => {
    const calls: string[] = [];
    const bot = new ChatbotService();
    await bot.handle(payload('Hello'), { env: env({ WHATSAPP_RECIPIENTS: '' }), fetchImpl: fetchImpl(calls) });
    await bot.handle(payload('Hello', 'wamid.2', '911111111111'), { env: env(), fetchImpl: fetchImpl(calls) });
    expect(calls).toEqual([]);
  });

  it('answers an admin and stays silent for everyone else once roles are loaded', async () => {
    setStaffDirectory([
      { phone: '919000000001', role: 'superadmin' },
      { phone: '919000000002', role: 'admin' },
    ]);
    const calls: string[] = [];
    const bot = new ChatbotService();
    await bot.handle(payload('Hello', 'wamid.user', '919876543210'), { env: env(), fetchImpl: fetchImpl(calls) });
    await bot.handle(payload('Hello', 'wamid.admin', '919000000002'), { env: env(), fetchImpl: fetchImpl(calls) });
    expect(calls).toEqual(['interactive:919000000002']);
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

  it('answers a greeting with every section as a one-tap button', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(payload('Hi', 'wamid.hi'), {
      env: env(),
      fetchImpl: capture(sent),
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    expect(sent).toHaveLength(1);
    const first = sent[0].interactive as { type: string; body: { text: string }; action: { button: string } };
    expect(first.type).toBe('list');
    expect(first.action.button).toBe('Menu');
    expect(first).not.toHaveProperty('header');
    expect(JSON.stringify(first)).not.toContain('Campaign updates');
    expect(first.body.text).toContain("Good evening, Sri. Lavu Sri Krishna Devarayalu Sir! I'm your Media Assistant.");
    expect(first.body.text).toContain('Choose a section.');
    const buttons = sent.flatMap(replyButtons);
    expect(buttons.map((button) => button.title)).toEqual(MAIN_BUTTONS.map((row) => row.title));
    expect(buttons.length).toBeGreaterThan(3);
    expect(JSON.stringify(sent)).not.toContain('http');
  });

  it('returns only the latest five news items when News is tapped, then the menu list', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(buttonPayload('news', 'News', 'wamid.news'), {
      env: env(),
      fetchImpl: capture(sent),
      news,
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    expect((sent[0].interactive as { type: string }).type).toBe('list');
    const body = messageText(sent[0]);
    expect(body).toContain('*News*');
    expect(body).not.toContain('Latest');
    expect(body.toLowerCase()).not.toContain('menu');
    expect(body).toContain('Cordon search in Narasaraopet');
    expect(body).toContain('Second item');
    expect(body).not.toContain('Sixth item');
    expect(body).not.toContain('Older road work');
    expect(body).not.toContain('http');
    expect(body).not.toContain("I'm your Media Assistant");
    expect(sent.flatMap(replyButtons).map((button) => button.id)).toEqual(MAIN_BUTTONS.map((row) => row.id));
  });

  it('returns to News, Visits, and More from the second More without another message', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(buttonPayload('home', 'More', 'wamid.menu'), {
      env: env(),
      fetchImpl: capture(sent),
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    expect(sent.flatMap(replyButtons).map((button) => button.title)).toEqual(MAIN_BUTTONS.map((row) => row.title));
    const body = (sent[0].interactive as { body: { text: string } }).body.text;
    expect(body).toBe(MAIN_MENU_TEXT);
    expect(body).not.toContain("I'm your Media Assistant");
  });

  it('keeps every section on the one menu list', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(buttonPayload('more', 'More', 'wamid.more'), {
      env: env(),
      fetchImpl: capture(sent),
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    const interactive = sent[0].interactive as { type: string; body: { text: string } };
    expect(interactive.type).toBe('list');
    expect(interactive.body.text).toBe(MAIN_MENU_TEXT);
    const buttons = sent.flatMap(replyButtons);
    expect(buttons.map((button) => button.id)).toEqual(['news', 'visits', 'grievances', 'projects', 'constituency', 'campaigns', 'analytics']);
    expect(buttons.some((button) => button.id === 'more')).toBe(false);
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
    const body = messageText(sent[0]);
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
    expect(sent[0]).toContain('*News*');
    expect(sent[0]).not.toContain("I'm your Media Assistant");
    expect(sent[0].toLowerCase()).not.toContain('menu');
    expect(sent[1]).toBe(MAIN_MENU_TEXT);
    expect(sent[2]).toContain("Good morning, Sri. Lavu Sri Krishna Devarayalu Sir! I'm your Media Assistant.");
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

  it('shows visits with Follow up and More, and never the lead number', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const db = {
      ensureConnected: async () => true,
      collection: () => ({
        find: () => ({
          sort: () => ({
            limit: () => ({
              toArray: async () => [{
                title: 'Hospital round',
                place: 'Vinukonda',
                visitDate: '2026-10-03',
                visitTime: '10:30',
                detail: 'Met the doctors',
                leadPhone: '919876543210',
                createdAt: '2026-10-03T01:00:00.000Z',
              }],
            }),
          }),
        }),
      }),
    };
    const bot = new ChatbotService(undefined, db as never);
    await bot.handle(buttonPayload('visits', 'Visits', 'wamid.visits'), {
      env: env(),
      fetchImpl: capture(sent),
      now: () => new Date('2026-10-03T04:00:00.000Z'),
    });
    const body = messageText(sent[0]);
    expect(body).toContain('*Hospital round*');
    expect(body.toLowerCase()).not.toContain('menu');
    expect(body).not.toContain('9876543210');
    expect(sent.flatMap(replyButtons).map((button) => button.id)).toEqual(VISIT_BUTTONS.map((row) => row.id));
  });

  it('returns to News, Visits, and More only after a follow-up is accepted', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const accepted = { sendAll: async () => ({ due: 2, sent: 1, failed: 1 }) };
    const bot = new ChatbotService(undefined, undefined, accepted as never);
    await bot.handle(buttonPayload('follow_up', 'Follow up', 'wamid.follow'), {
      env: env(),
      fetchImpl: capture(sent),
      now: () => new Date('2026-10-03T04:00:00.000Z'),
    });
    const interactive = sent[0].interactive as { body: { text: string } };
    expect(interactive.body.text).toBe(FOLLOW_UP_SENT);
    expect(sent.flatMap(replyButtons).map((button) => button.title)).toEqual(MAIN_BUTTONS.map((row) => row.title));
  });

  it('answers Follow up before the visit messages finish', async () => {
    const sent: Array<Record<string, unknown>> = [];
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const follow = {
      readyToSend: async () => true,
      sendAll: () => gate.then(() => ({ due: 2, sent: 1, failed: 0 })),
    };
    const bot = new ChatbotService(undefined, undefined, follow as never);
    await bot.handle(buttonPayload('follow_up', 'Follow up', 'wamid.follow-now'), {
      env: env(),
      fetchImpl: capture(sent),
      now: () => new Date('2026-10-03T04:00:00.000Z'),
    });
    const interactive = sent[0].interactive as { body: { text: string } };
    expect(interactive.body.text).toBe(FOLLOW_UP_SENT);
    expect(sent.flatMap(replyButtons).map((button) => button.id)).toEqual(MAIN_BUTTONS.map((row) => row.id));
    release();
    await gate;
  });

  it('stays on the visit list when there is nobody to message', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const follow = {
      readyToSend: async () => false,
      sendAll: async () => {
        throw new Error('should not send');
      },
    };
    const bot = new ChatbotService(undefined, undefined, follow as never);
    await bot.handle(buttonPayload('follow_up', 'Follow up', 'wamid.follow-empty'), {
      env: env(),
      fetchImpl: capture(sent),
      records: { visits: [{ title: 'Ward meeting', detail: 'Ipur', status: 'Manual', date: '2026-10-03' }] },
      now: () => new Date('2026-10-03T04:00:00.000Z'),
    });
    expect(messageText(sent[0])).toContain('Ward meeting');
    expect(messageText(sent[0]).toLowerCase()).not.toContain('menu');
    expect(sent.flatMap(replyButtons).map((button) => button.id)).toEqual(VISIT_BUTTONS.map((row) => row.id));
  });

  it('stays on the visit list when no follow-up is accepted', async () => {
    const sent: Array<Record<string, unknown>> = [];
    const refused = { sendAll: async () => ({ due: 1, sent: 0, failed: 1 }) };
    const bot = new ChatbotService(undefined, undefined, refused as never);
    await bot.handle(buttonPayload('follow_up', 'Follow up', 'wamid.follow-fail'), {
      env: env(),
      fetchImpl: capture(sent),
      records: { visits: [{ title: 'Ward meeting', detail: 'Ipur', status: 'Manual', date: '2026-10-03' }] },
      now: () => new Date('2026-10-03T04:00:00.000Z'),
    });
    expect(messageText(sent[0])).toContain('Ward meeting');
    expect(messageText(sent[0])).not.toContain(FOLLOW_UP_SENT);
    expect(messageText(sent[0]).toLowerCase()).not.toContain('menu');
    expect(sent.flatMap(replyButtons).map((button) => button.id)).toEqual(VISIT_BUTTONS.map((row) => row.id));
  });

  it('saves a person message as a grievance and sends only a receipt', async () => {
    setStaffDirectory([
      { phone: '919000000002', role: 'admin' },
      { phone: '918885230708', role: 'person', name: 'Udatha Sravani' },
    ]);
    const { rows, db } = memoryRecords();
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService(undefined, db as never);
    await bot.handle(payload('The road is broken', 'wamid.road', '918885230708'), {
      env: env(),
      fetchImpl: capture(sent),
    });
    expect(rows).toEqual([expect.objectContaining({
      section: 'grievances',
      title: 'Udatha Sravani',
      detail: 'Normal — The road is broken',
      priority: 'normal',
      status: 'Open',
      createdBy: 'Udatha Sravani',
      sourceMessageId: 'wamid.road',
    })]);
    expect(sent).toHaveLength(1);
    expect(sent[0].type).toBe('text');
    expect(sent[0].to).toBe('918885230708');
    expect((sent[0].text as { body: string }).body).toBe(GRIEVANCE_RECEIPT);
    expect(JSON.stringify(sent)).not.toContain('"type":"list"');
  });

  it('does not save the same grievance twice', async () => {
    setStaffDirectory([{ phone: '918919537879', role: 'person', name: 'Balaji' }]);
    const { rows, db } = memoryRecords();
    const first: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService(undefined, db as never);
    const body = payload('Water supply stopped', 'wamid.water', '918919537879');
    await bot.handle(body, { env: env(), fetchImpl: capture(first) });
    const again: Array<Record<string, unknown>> = [];
    const retry = new ChatbotService(undefined, db as never);
    await retry.handle(body, { env: env(), fetchImpl: capture(again) });
    expect(rows).toHaveLength(1);
    expect(first).toHaveLength(1);
    expect(again).toEqual([]);
  });

  it('shows a saved grievance when an admin opens Grievances', async () => {
    setStaffDirectory([
      { phone: '919000000002', role: 'admin' },
      { phone: '918885230708', role: 'person', name: 'Udatha Sravani' },
    ]);
    const { db } = memoryRecords();
    const bot = new ChatbotService(undefined, db as never);
    await bot.handle(payload('Street light is out', 'wamid.light', '918885230708'), {
      env: env(),
      fetchImpl: capture([]),
    });
    const sent: Array<Record<string, unknown>> = [];
    await bot.handle(buttonPayload('grievances', 'Grievances', 'wamid.ask', '919000000002'), {
      env: env(),
      fetchImpl: capture(sent),
    });
    const body = messageText(sent[0]);
    expect(body).toContain('Udatha Sravani');
    expect(body).toContain('Street light is out');
    expect(sent).toHaveLength(1);
    expect(sent[0].type).toBe('interactive');
  });

  it('stores a photo from a person as a short note', async () => {
    setStaffDirectory([{ phone: '918919537879', role: 'person', name: 'Balaji' }]);
    const { rows, db } = memoryRecords();
    const bot = new ChatbotService(undefined, db as never);
    await bot.handle({
      object: 'whatsapp_business_account',
      entry: [{ changes: [{ value: { messages: [{ from: '918919537879', id: 'wamid.photo', timestamp: '1', type: 'image', image: { id: 'media' } }] } }] }],
    }, { env: env(), fetchImpl: capture([]) });
    expect(rows[0]).toMatchObject({ title: 'Balaji', detail: 'Normal — Sent a photo.', status: 'Open', priority: 'normal' });
  });

  it('marks urgent grievance words as high priority', () => {
    expect(classifyGrievance('No drinking water in the colony').priority).toBe('high');
    expect(classifyGrievance('Please share the meeting time').priority).toBe('normal');
  });

  it('gives the MP six updated items and keeps an admin at five', async () => {
    setStaffDirectory([
      { phone: '919912514034', role: 'mp', name: 'Shri Lavu Sri Krishna Devarayalu' },
      { phone: '919876543210', role: 'admin' },
    ]);
    const mpSent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(buttonPayload('news', 'News', 'wamid.mp-news', '919912514034'), {
      env: env(),
      fetchImpl: capture(mpSent),
      news,
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    const mpBody = messageText(mpSent[0]);
    expect(mpBody).toContain('6. *Sixth item*');
    expect(mpBody).not.toContain('Older road work');
    const adminSent: Array<Record<string, unknown>> = [];
    await bot.handle(buttonPayload('news', 'News', 'wamid.admin-news', '919876543210'), {
      env: env(),
      fetchImpl: capture(adminSent),
      news,
      now: () => new Date('2026-09-28T13:49:00Z'),
    });
    const adminBody = messageText(adminSent[0]);
    expect(adminBody).toContain('5. *Fifth item*');
    expect(adminBody).not.toContain('Sixth item');
  });

  it('shows the MP grievances as options with high priority first', async () => {
    setStaffDirectory([{ phone: '919553147457', role: 'mp' }]);
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(buttonPayload('grievances', 'Grievances', 'wamid.mp-g', '919553147457'), {
      env: env(),
      fetchImpl: capture(sent),
      records: {
        grievances: [
          { id: 'normal-1', title: 'Street lights', detail: 'Lights are out', status: 'Open', date: '2026-10-10T00:00:00Z', priority: 'normal' },
          { id: 'high-1', title: 'No drinking water', detail: 'Colony has no water', status: 'Open', date: '2026-10-09T00:00:00Z', priority: 'high' },
        ],
      },
    });
    const rows = sent.flatMap(replyButtons);
    expect(rows.map((row) => row.id)).toEqual(['g:high-1', 'g:normal-1', 'home']);
    expect(rows[0]).toMatchObject({ title: 'No drinking water' });
    expect(JSON.stringify(sent)).toContain('High priority');
    await bot.handle(buttonPayload('g:high-1', 'No drinking water', 'wamid.mp-pick', '919553147457'), {
      env: env(),
      fetchImpl: capture(sent),
      records: {
        grievances: [
          { id: 'normal-1', title: 'Street lights', detail: 'Lights are out', status: 'Open', date: '2026-10-10T00:00:00Z', priority: 'normal' },
          { id: 'high-1', title: 'No drinking water', detail: 'Colony has no water', status: 'Open', date: '2026-10-09T00:00:00Z', priority: 'high' },
        ],
      },
    });
    expect(messageText(sent[1])).toContain('Colony has no water');
  });

  it('tells the super admin when a person files a grievance', async () => {
    setStaffDirectory([
      { phone: '916281168530', role: 'superadmin', name: 'Sarojininaidu' },
      { phone: '918885230708', role: 'person', name: 'Udatha Sravani' },
    ]);
    const { rows, db } = memoryRecords();
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService(undefined, db as never);
    await bot.handle(payload('No drinking water since morning', 'wamid.water-g', '918885230708'), {
      env: env(),
      fetchImpl: capture(sent),
    });
    expect(rows[0]).toMatchObject({ priority: 'high', title: 'Udatha Sravani' });
    expect(sent.map((message) => message.to)).toEqual(['918885230708', '916281168530']);
    expect((sent[1].text as { body: string }).body).toContain('Udatha Sravani');
    expect((sent[1].text as { body: string }).body).toContain('High priority');
    expect(sent.every((message) => message.type === 'text')).toBe(true);
  });

  it('lets the super admin open the same grievance list as the MP', async () => {
    setStaffDirectory([{ phone: '916281168530', role: 'superadmin', name: 'Sarojininaidu' }]);
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService();
    await bot.handle(buttonPayload('grievances', 'Grievances', 'wamid.super-g', '916281168530'), {
      env: env(),
      fetchImpl: capture(sent),
      records: {
        grievances: [
          { id: 'normal-1', title: 'Street lights', detail: 'Lights are out', status: 'Open', date: '2026-10-10T00:00:00Z', priority: 'normal' },
          { id: 'high-1', title: 'No drinking water', detail: 'Colony has no water', status: 'Open', date: '2026-10-09T00:00:00Z', priority: 'high' },
        ],
      },
    });
    expect(sent.flatMap(replyButtons).map((row) => row.id)).toEqual(['g:high-1', 'g:normal-1', 'home']);
  });

  it('stores sample campaigns when that section is empty', async () => {
    setStaffDirectory([{ phone: '919876543210', role: 'admin' }]);
    const { rows, db } = memoryRecords();
    const sent: Array<Record<string, unknown>> = [];
    const bot = new ChatbotService(undefined, db as never);
    await bot.handle(buttonPayload('campaigns', 'Campaigns', 'wamid.camp'), {
      env: env(),
      fetchImpl: capture(sent),
    });
    expect(rows.map((row) => row.title)).toEqual(['Door to door', 'Youth meeting', 'Rythu bharosa', 'Health camp']);
    expect(messageText(sent[0])).toContain('Door to door');
    expect(messageText(sent[0])).toContain('Health camp');
  });

  it('caps a section at five lines', () => {
    const body = formatSection('News', ['a', 'b', 'c', 'd', 'e', 'f']);
    expect(body).toContain('5. e');
    expect(body).not.toContain('Latest');
    expect(body).not.toContain('6. f');
  });
});
