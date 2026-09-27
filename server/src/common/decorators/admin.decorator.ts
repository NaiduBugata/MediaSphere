import { applyDecorators, UseGuards } from '@nestjs/common';
import { AdminAuthGuard } from '../guards/admin-auth.guard';

/**
 * Marks a route as admin-only (HMAC bearer / X-Admin-Token).
 * Equivalent to the `if not _require_admin(): return _unauthorized()` prelude
 * on every Flask `/api/admin/*` handler.
 */
export function AdminOnly(): MethodDecorator & ClassDecorator {
  return applyDecorators(UseGuards(AdminAuthGuard));
}
