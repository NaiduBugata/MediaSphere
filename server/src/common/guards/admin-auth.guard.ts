import {
  CanActivate,
  ExecutionContext,
  HttpException,
  HttpStatus,
  Injectable,
} from '@nestjs/common';
import { Request } from 'express';
import { AdminAuthService } from '../../admin/auth/admin-auth.service';

/**
 * Mirrors Flask `admin/routes.py::_require_admin` + `_unauthorized`.
 * Accepts `Authorization: Bearer <token>` or `X-Admin-Token: <token>`.
 */
@Injectable()
export class AdminAuthGuard implements CanActivate {
  constructor(private readonly auth: AdminAuthService) {}

  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest<Request>();
    const adminTokenHeader = req.headers['x-admin-token'];
    const header =
      req.headers.authorization ||
      (typeof adminTokenHeader === 'string' ? adminTokenHeader : undefined) ||
      null;

    if (!this.auth.verifySessionToken(header)) {
      throw new HttpException(
        { error: 'Unauthorized', status: 'unauthorized' },
        HttpStatus.UNAUTHORIZED,
      );
    }
    return true;
  }
}
