import { ConfigService } from '@nestjs/config';
import { AdminAuthService } from './admin-auth.service';

/**
 * Golden signatures below were produced by the Flask implementation itself:
 *
 *   ADMIN_SESSION_SECRET=test-secret python -c \
 *     "from admin import auth; print(auth._sign('admin:1700000000'))"
 *
 * so this suite fails if the Nest HMAC ever drifts from server/admin/auth.py.
 */
const SECRET = 'test-secret';
const PASSWORD = 'test-password';
const SIG_EXPIRED =
  'cfd8234ac49baf713bd818208b06f80bd572e3d2b6a47dd7b1f00dba1d6f05d2'; // admin:1700000000
const SIG_FUTURE =
  '3054a0bdcac491ad88ec4195838ea02085f4c99688344761b25d1800be2694ce'; // admin:9999999999

function makeService(
  overrides: Record<string, unknown> = {},
): AdminAuthService {
  const values: Record<string, unknown> = {
    'admin.username': 'Admin',
    'admin.password': PASSWORD,
    'admin.sessionSecret': SECRET,
    'admin.sessionTtlSeconds': 28800,
    ...overrides,
  };
  const config = {
    get: (key: string) => values[key],
  } as unknown as ConfigService;
  return new AdminAuthService(config);
}

describe('AdminAuthService (Flask admin/auth.py parity)', () => {
  it('produces the same HMAC-SHA256 signature as Flask', () => {
    const service = makeService();
    const token = `admin:9999999999.${SIG_FUTURE}`;
    expect(service.verifySessionToken(token)).toBe(true);
  });

  it('issues admin:{exp}.{sig} tokens that verify', () => {
    const service = makeService();
    const session = service.issueSessionToken();
    expect(session.token_type).toBe('Bearer');
    expect(session.token.startsWith('admin:')).toBe(true);
    expect(session.token.split('.')[0]).toBe(`admin:${session.expires_at}`);
    expect(service.verifySessionToken(session.token)).toBe(true);
  });

  it('enforces the 300s TTL floor', () => {
    const service = makeService();
    const before = Math.floor(Date.now() / 1000);
    const session = service.issueSessionToken(1);
    expect(session.expires_at).toBeGreaterThanOrEqual(before + 300);
  });

  it('accepts a Bearer prefix case-insensitively', () => {
    const service = makeService();
    expect(
      service.verifySessionToken(`bearer admin:9999999999.${SIG_FUTURE}`),
    ).toBe(true);
    expect(
      service.verifySessionToken(`BEARER  admin:9999999999.${SIG_FUTURE}`),
    ).toBe(true);
  });

  it('rejects expired, wrong-role, tampered and malformed tokens', () => {
    const service = makeService();
    expect(service.verifySessionToken(`admin:1700000000.${SIG_EXPIRED}`)).toBe(
      false,
    );
    expect(service.verifySessionToken(`user:9999999999.${SIG_FUTURE}`)).toBe(
      false,
    );
    expect(service.verifySessionToken(`admin:9999999999.${SIG_EXPIRED}`)).toBe(
      false,
    );
    expect(service.verifySessionToken('admin:9999999999')).toBe(false);
    expect(service.verifySessionToken('')).toBe(false);
    expect(service.verifySessionToken(null)).toBe(false);
    expect(service.verifySessionToken('admin:notanumber.deadbeef')).toBe(false);
  });

  it('rejects every token when admin auth is unconfigured', () => {
    const service = makeService({ 'admin.password': '' });
    expect(service.isConfigured()).toBe(false);
    expect(service.verifySessionToken(`admin:9999999999.${SIG_FUTURE}`)).toBe(
      false,
    );
  });

  it('signs with ADMIN_PASSWORD when ADMIN_SESSION_SECRET is absent', () => {
    const withSecret = makeService();
    const withoutSecret = makeService({ 'admin.sessionSecret': '' });
    expect(withoutSecret.signingSecret()).toBe(PASSWORD);
    expect(withSecret.signingSecret()).toBe(SECRET);
    // A token minted under the password secret must not verify under the other.
    const token = withoutSecret.issueSessionToken().token;
    expect(withoutSecret.verifySessionToken(token)).toBe(true);
    expect(withSecret.verifySessionToken(token)).toBe(false);
  });

  it('verifies credentials with trimmed, case-insensitive username', () => {
    const service = makeService();
    expect(service.verifyCredentials(' aDmIn ', PASSWORD)).toBe(true);
    expect(service.verifyCredentials('nope', PASSWORD)).toBe(false);
    expect(service.verifyCredentials('', PASSWORD)).toBe(false);
    expect(service.verifyCredentials('Admin', 'wrong')).toBe(false);
    expect(service.verifyCredentials('Admin', null)).toBe(false);
  });

  it('skips the username check when ADMIN_USERNAME is unset (legacy)', () => {
    const service = makeService({ 'admin.username': '' });
    expect(service.verifyCredentials('', PASSWORD)).toBe(true);
    expect(service.verifyCredentials(null, PASSWORD)).toBe(true);
    expect(service.verifyCredentials(null, 'wrong')).toBe(false);
  });

  it('refuses credentials when no password is configured', () => {
    const service = makeService({ 'admin.password': '' });
    expect(service.verifyCredentials('Admin', '')).toBe(false);
    expect(service.verifyCredentials('Admin', PASSWORD)).toBe(false);
  });
});
