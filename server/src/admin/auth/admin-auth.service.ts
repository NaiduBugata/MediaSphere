import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createHmac, timingSafeEqual } from 'node:crypto';

export interface AdminSession {
  token: string;
  expires_at: number;
  token_type: 'Bearer';
}

/**
 * Port of Flask `server/admin/auth.py`.
 *
 * Token shape: `admin:{exp}.{hexSha256Hmac}` signed with
 * ADMIN_SESSION_SECRET -> ADMIN_PASSWORD -> dev fallback (same precedence).
 * Secrets are never logged.
 */
@Injectable()
export class AdminAuthService {
  constructor(private readonly config: ConfigService) {}

  adminUsername(): string {
    return (this.config.get<string>('admin.username') || '').trim();
  }

  /** Prefer ADMIN_PASSWORD; fall back to PIPELINE_ADMIN_TOKEN (resolved in config). */
  adminPassword(): string {
    return (this.config.get<string>('admin.password') || '').trim();
  }

  signingSecret(): string {
    return (
      (this.config.get<string>('admin.sessionSecret') || '').trim() ||
      this.adminPassword() ||
      'mediasphere-admin-dev-insecure'
    );
  }

  isConfigured(): boolean {
    return Boolean(this.adminPassword());
  }

  private sign(payload: string): string {
    return createHmac('sha256', Buffer.from(this.signingSecret(), 'utf8'))
      .update(Buffer.from(payload, 'utf8'))
      .digest('hex');
  }

  /** hmac.compare_digest equivalent (constant time, length-safe). */
  private compareDigest(a: string, b: string): boolean {
    const left = Buffer.from(a, 'utf8');
    const right = Buffer.from(b, 'utf8');
    if (left.length !== right.length) {
      // Still burn a comparison so timing does not leak length trivially.
      timingSafeEqual(left, left);
      return false;
    }
    return timingSafeEqual(left, right);
  }

  issueSessionToken(ttlSeconds?: number): AdminSession {
    const ttl =
      ttlSeconds || this.config.get<number>('admin.sessionTtlSeconds') || 28800;
    const exp = Math.floor(Date.now() / 1000) + Math.max(300, ttl);
    const payload = `admin:${exp}`;
    return {
      token: `${payload}.${this.sign(payload)}`,
      expires_at: exp,
      token_type: 'Bearer',
    };
  }

  verifySessionToken(token: string | null | undefined): boolean {
    if (!token || !this.isConfigured()) return false;
    let raw = String(token).trim();
    if (raw.toLowerCase().startsWith('bearer ')) {
      raw = raw.slice(7).trim();
    }
    if (!raw.includes('.')) return false;

    const splitAt = raw.lastIndexOf('.');
    const payload = raw.slice(0, splitAt);
    const signature = raw.slice(splitAt + 1);
    if (!this.compareDigest(signature, this.sign(payload))) return false;

    const sep = payload.indexOf(':');
    if (sep < 0) return false;
    const role = payload.slice(0, sep);
    const expRaw = payload.slice(sep + 1).trim();
    if (role !== 'admin') return false;
    if (!/^[+-]?\d+$/.test(expRaw)) return false;
    return parseInt(expRaw, 10) >= Math.floor(Date.now() / 1000);
  }

  /**
   * Flask verify_credentials: password must match; username only checked when
   * ADMIN_USERNAME is configured (case-insensitive, trimmed).
   */
  verifyCredentials(
    username: string | null | undefined,
    password: string | null | undefined,
  ): boolean {
    const expectedPassword = this.adminPassword();
    if (!expectedPassword || password === null || password === undefined) {
      return false;
    }
    if (!this.compareDigest(String(password), expectedPassword)) return false;

    const expectedUser = this.adminUsername();
    if (!expectedUser) return true;
    if (username === null || username === undefined) return false;
    return this.compareDigest(
      String(username).trim().toLowerCase(),
      expectedUser.toLowerCase(),
    );
  }
}
