import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpException,
  HttpStatus,
  Post,
} from '@nestjs/common';
import { AdminAuthService } from './admin-auth.service';
import { AdminOnly } from '../../common/decorators/admin.decorator';

/**
 * Mirrors Flask `admin_bp` auth routes (url_prefix `/api/admin`).
 * Status codes: 200 ok / 403 invalid credentials / 503 not configured / 401 guard.
 */
@Controller('api/admin/auth')
export class AdminAuthController {
  constructor(private readonly auth: AdminAuthService) {}

  @Post('login')
  @HttpCode(HttpStatus.OK)
  login(@Body() body: Record<string, unknown> | undefined) {
    if (!this.auth.isConfigured()) {
      throw new HttpException(
        {
          error:
            'Admin auth is not configured. Set ADMIN_PASSWORD (and optionally ADMIN_USERNAME).',
          status: 'disabled',
        },
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
    const payload = body && typeof body === 'object' ? body : {};
    // Flask: payload.get("username") or payload.get("email") or ""
    const username = String(payload.username || payload.email || '');
    const password = String(payload.password || payload.token || '');

    if (!this.auth.verifyCredentials(username, password)) {
      throw new HttpException(
        { error: 'Invalid credentials', status: 'forbidden' },
        HttpStatus.FORBIDDEN,
      );
    }
    return { status: 'ok', ...this.auth.issueSessionToken() };
  }

  /** Stateless tokens — the client discards. Kept for UX parity. */
  @Post('logout')
  @HttpCode(HttpStatus.OK)
  logout() {
    return { status: 'ok' };
  }

  @Get('me')
  @AdminOnly()
  me() {
    return { status: 'ok', role: 'admin' };
  }
}
