import { ChatbotService, toWhatsAppFormat } from './chatbot.service';

const document = {
  id: 'assistant-001',
  title: 'Assistant Identity',
  content: 'I am a knowledge-based AI assistant.',
  keywords: ['assistant', 'who', 'identity'],
};

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

function env(overrides: NodeJS.ProcessEnv = {}): NodeJS.ProcessEnv {
  return {
    CHATBOT_ENABLED: 'true',
    WHATSAPP_ENABLED: 'true',
    WHATSAPP_RECIPIENTS: '919876543210',
    WHATSAPP_ACCESS_TOKEN: 'test-token',
    WHATSAPP_PHONE_NUMBER_ID: '123',
    GROQ_API_KEY: 'test-key',
    ...overrides,
  };
}

function fetchImpl(calls: string[]): typeof fetch {
  return (async (url: string | URL | Request, init?: RequestInit) => {
    const href = String(url);
    calls.push(href);
    if (href.includes('groq.com')) {
      return {
        ok: true,
        json: async () => ({ choices: [{ message: { content: 'I am a knowledge-based AI assistant.' } }] }),
      } as Response;
    }
    const body = JSON.parse(String(init?.body || '{}')) as { to?: string; type?: string };
    calls.push(`${body.type}:${body.to}`);
    return { ok: true, json: async () => ({ messages: [{ id: 'out' }] }) } as Response;
  }) as typeof fetch;
}

describe('ChatbotService', () => {
  it('replies to an allowlisted text and ignores a second delivery of the same message', async () => {
    const calls: string[] = [];
    const bot = new ChatbotService();
    bot['documents'] = [document];
    await bot.handle(payload('Who are you?'), { env: env(), fetchImpl: fetchImpl(calls), documents: [document] });
    await bot.handle(payload('Who are you?'), { env: env(), fetchImpl: fetchImpl(calls), documents: [document] });
    expect(calls.filter((call) => call.startsWith('text:'))).toEqual(['text:919876543210']);
  });

  it('does not call Groq when the allowlist is empty or the sender is not listed', async () => {
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

  it('gives Groq the stored news so a vague request for updates can be answered', async () => {
    const prompts: string[] = [];
    const recording = (async (url: string | URL | Request, init?: RequestInit) => {
      if (String(url).includes('groq.com')) prompts.push(String(init?.body || ''));
      return { ok: true, json: async () => ({ choices: [{ message: { content: 'Update' } }], messages: [{ id: 'out' }] }) } as Response;
    }) as typeof fetch;
    const news = [{
      title: 'Cordon search in Narasaraopet',
      summary: 'Police searched the Pedda Cheruvu area.',
      category: 'Crime',
      sentiment: 'Statement',
      severity: 'moderate',
      place: 'Narasaraopet, Palnadu',
      source: 'youtube',
      url: 'https://www.youtube.com/watch?v=x',
      publishedAt: '2026-09-27T07:26:08Z',
      collectedAt: '2026-09-28T04:32:17Z',
    }];
    const bot = new ChatbotService();
    await bot.handle(payload('can you tell me latest updates', 'wamid.news'), { env: env(), fetchImpl: recording, documents: [document], news });
    expect(prompts).toHaveLength(1);
    const body = JSON.parse(prompts[0]) as { messages: Array<{ content: string }>; reasoning_effort?: string };
    expect(body.messages[0].content).toContain('Cordon search in Narasaraopet');
    expect(body.messages[0].content).toContain('Narasaraopet, Palnadu');
    expect(body.reasoning_effort).toBe('low');
  });

  it('tries the next Groq key when the first one is rejected', async () => {
    const keys: string[] = [];
    const calls: string[] = [];
    const rotating = (async (url: string | URL | Request, init?: RequestInit) => {
      if (String(url).includes('groq.com')) {
        const auth = String((init?.headers as Record<string, string>).Authorization);
        keys.push(auth);
        if (auth.endsWith('key-1')) return { ok: false, status: 429, json: async () => ({}) } as Response;
        return { ok: true, json: async () => ({ choices: [{ message: { content: 'Hi' } }] }) } as Response;
      }
      calls.push('send');
      return { ok: true, json: async () => ({ messages: [{ id: 'out' }] }) } as Response;
    }) as typeof fetch;
    const bot = new ChatbotService();
    await bot.handle(payload('Hi', 'wamid.rotate'), {
      env: env({ GROQ_API_KEY: '', GROQ_API_KEY_1: 'key-1', GROQ_API_KEY_2: 'key-2' }),
      fetchImpl: rotating,
      documents: [document],
      news: [],
    });
    expect(keys).toEqual(['Bearer key-1', 'Bearer key-2']);
    expect(calls).toEqual(['send']);
  });

  it('converts markdown bold and headings to WhatsApp formatting', () => {
    expect(toWhatsAppFormat('## Today\n**Narasaraopet** – *Crime* – __theft__')).toBe('Today\n*Narasaraopet* – *Crime* – _theft_');
  });

  it('lets a failed send be tried again', async () => {
    const bot = new ChatbotService();
    const failing = (async () => ({ ok: false, json: async () => ({}) })) as typeof fetch;
    await bot.handle(payload('Hi', 'wamid.fail'), { env: env(), fetchImpl: failing, documents: [document] });
    const calls: string[] = [];
    await bot.handle(payload('Hi', 'wamid.fail'), { env: env(), fetchImpl: fetchImpl(calls), documents: [document] });
    expect(calls.some((call) => call.startsWith('text:'))).toBe(true);
  });
});
