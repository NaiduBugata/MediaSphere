import { ChatbotService } from './chatbot.service';

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

  it('lets a failed send be tried again', async () => {
    const bot = new ChatbotService();
    const failing = (async () => ({ ok: false, json: async () => ({}) })) as typeof fetch;
    await bot.handle(payload('Hi', 'wamid.fail'), { env: env(), fetchImpl: failing, documents: [document] });
    const calls: string[] = [];
    await bot.handle(payload('Hi', 'wamid.fail'), { env: env(), fetchImpl: fetchImpl(calls), documents: [document] });
    expect(calls.some((call) => call.startsWith('text:'))).toBe(true);
  });
});
