import { Logger } from '@nestjs/common';

const logger = new Logger('EnvValidation');

export function validateEnv(env: NodeJS.ProcessEnv): void {
  if (!env.NEON_DATABASE_URL) {
    logger.warn(
      'NEON_DATABASE_URL is not set. Database routes will fail until configured.',
    );
  }
  if (env.NODE_ENV === 'production' && !(env.CORS_ORIGINS || '').trim()) {
    logger.warn(
      'CORS_ORIGINS is unset. Add the Vercel domain. *.vercel.app previews stay allowed unless CORS_ALLOW_VERCEL_PREVIEWS=false.',
    );
  }
  if (
    env.NODE_ENV === 'production' &&
    !(env.ADMIN_SESSION_SECRET || '').trim() &&
    !(env.ADMIN_PASSWORD || '').trim()
  ) {
    logger.warn(
      'ADMIN_SESSION_SECRET is unset. Set it before exposing admin routes.',
    );
  }
}
