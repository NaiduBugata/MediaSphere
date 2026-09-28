import { notifyPendingEmail } from './incremental-email';

describe('notifyPendingEmail', () => {
  const previous: Record<string, string | undefined> = {};

  beforeEach(() => {
    for (const key of [
      'EMAIL_ENABLED',
      'EMAIL_PROVIDER',
      'RESEND_API_KEY',
      'SMTP_FROM_EMAIL',
      'REPORT_RECIPIENTS',
      'SMTP_MAX_RETRIES',
      'SMTP_RETRY_BACKOFF_SECONDS',
    ]) {
      previous[key] = process.env[key];
    }
    process.env.EMAIL_ENABLED = 'true';
    process.env.EMAIL_PROVIDER = 'resend';
    process.env.RESEND_API_KEY = 'test-key';
    process.env.SMTP_FROM_EMAIL = 'news@example.com';
    process.env.REPORT_RECIPIENTS = 'desk@example.com';
    process.env.SMTP_MAX_RETRIES = '1';
    process.env.SMTP_RETRY_BACKOFF_SECONDS = '0';
  });

  afterEach(() => {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });

  it('does not read pending articles when email is disabled', async () => {
    process.env.EMAIL_ENABLED = 'false';
    const findPending = jest.fn();
    const result = await notifyPendingEmail({ findPending, markSent: jest.fn() });
    expect(result.skipped).toBe(true);
    expect(findPending).not.toHaveBeenCalled();
  });

  it('sends one Resend message and marks the article emailed', async () => {
    const fetchImpl = jest.fn().mockResolvedValue({
      ok: true,
      text: async () => '',
    });
    const markSent = jest.fn().mockResolvedValue(undefined);
    const result = await notifyPendingEmail({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      findPending: async () => [
        { post_id: 'lokal-1', title: 'Water supply', summary: 'Ward 14', source: 'lokal', source_url: 'https://example.com/a' },
      ],
      markSent,
    });
    expect(result).toEqual({ sent: 1, failed: 0, skipped: false, pending: 1, lastError: null });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(String(fetchImpl.mock.calls[0][0])).toBe('https://api.resend.com/emails');
    expect(markSent).toHaveBeenCalledWith('lokal-1', expect.any(String));
  });

  it('leaves the article pending when Resend rejects the message', async () => {
    const fetchImpl = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: async () => 'rejected',
    });
    const markSent = jest.fn();
    const result = await notifyPendingEmail({
      fetchImpl: fetchImpl as unknown as typeof fetch,
      findPending: async () => [{ post_id: 'lokal-2', title: 'Road', source: 'sakshi' }],
      markSent,
    });
    expect(result.failed).toBe(1);
    expect(result.lastError).toContain('Resend API 422');
    expect(markSent).not.toHaveBeenCalled();
  });
});
