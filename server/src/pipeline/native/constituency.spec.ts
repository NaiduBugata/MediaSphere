import { scoreConstituency, validateConstituency } from './constituency';

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

describe('borderline constituency check', () => {
  const original = { ...process.env };

  afterEach(() => {
    process.env = { ...original };
  });

  it('keeps a strong Narasaraopet match and drops an unrelated story', () => {
    expect(scoreConstituency('నరసరావుపేట లో రోడ్డు పనులు').valid).toBe(true);
    expect(scoreConstituency('A quiet afternoon with no place names').reason).toBe('score_below_threshold');
    expect(scoreConstituency('Mumbai cinema premiere tonight').reason).toBe('negative_filter');
  });

  it('asks Groq only for a borderline village mention', async () => {
    process.env.GROQ_API_KEY = 'test-key';
    process.env.CONSTITUENCY_AI_VALIDATION = 'true';
    const calls: string[] = [];
    const fetchImpl = (async (url: string) => {
      calls.push(String(url));
      return jsonResponse({ choices: [{ message: { content: 'YES' } }] });
    }) as typeof fetch;

    const accepted = await validateConstituency({ title: 'Perecherla school day', content: 'A local event.' }, fetchImpl);
    expect(accepted.valid).toBe(true);
    expect(accepted.reason).toBe('ai_yes');
    expect(accepted.ai_decision).toBe('YES');
    expect(calls).toEqual(['https://api.groq.com/openai/v1/chat/completions']);

    const rejected = await validateConstituency(
      { title: 'Perecherla school day', content: 'A local event.' },
      (async () => jsonResponse({ choices: [{ message: { content: 'NO' } }] })) as typeof fetch,
    );
    expect(rejected.valid).toBe(false);
    expect(rejected.reason).toBe('ai_no');
  });

  it('does not call Groq when AI validation is off or the score is already decided', async () => {
    process.env.GROQ_API_KEY = 'test-key';
    process.env.CONSTITUENCY_AI_VALIDATION = 'false';
    const fetchImpl = (async () => {
      throw new Error('groq should not be called');
    }) as typeof fetch;
    const borderline = await validateConstituency({ title: 'Perecherla fair', content: 'crowd' }, fetchImpl);
    expect(borderline.reason).toBe('borderline_no_ai');
    const strong = await validateConstituency({ title: 'Narasaraopet roads', content: 'repair' }, fetchImpl);
    expect(strong.reason).toBe('score_accept');
  });

  it('treats a missing key as uncertain and rejects the article', async () => {
    delete process.env.GROQ_API_KEY;
    delete process.env.GROQ_API_KEYS;
    for (const key of Object.keys(process.env)) {
      if (key.startsWith('GROQ_API_KEY')) delete process.env[key];
    }
    process.env.CONSTITUENCY_AI_VALIDATION = 'true';
    const result = await validateConstituency({ title: 'Perecherla fair', content: 'crowd' }, fetch);
    expect(result.reason).toBe('ai_uncertain');
    expect(result.valid).toBe(false);
  });
});
