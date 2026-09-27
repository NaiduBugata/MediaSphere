import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { App } from 'supertest/types';
import { AppModule } from './../src/app.module';

/**
 * Phase 3 control-plane e2e.
 *
 * SAFETY: this suite is deliberately read-only / rejection-only. It never
 * supplies a valid X-Pipeline-Admin-Token and never calls fetch/trigger or
 * fetch/retry, because those would start a real pipeline cycle against the
 * production Mongo that ../server/.env points at. The scheduler is also forced
 * off before the module is built so no interval or catch-up can arm.
 */
const UNAUTHORIZED = { error: 'Unauthorized', status: 'unauthorized' };

describe('Admin + pipeline control plane (e2e)', () => {
  let app: INestApplication<App>;

  beforeAll(async () => {
    // Set before compile(): the configuration factory and the scheduler's
    // onModuleInit both run during module init, not at import time.
    process.env.PIPELINE_EXECUTOR = 'python';
    process.env.PIPELINE_ON_API = 'false';
    process.env.PIPELINE_CATCHUP_ON_START = 'false';

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.enableShutdownHooks();
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  const server = () => request(app.getHttpServer());

  describe('guard (Flask _require_admin parity)', () => {
    const guarded: Array<[string, string]> = [
      ['get', '/api/admin/auth/me'],
      ['get', '/api/admin/fetch/status'],
      ['get', '/api/admin/fetch/history'],
      ['get', '/api/admin/fetch/some-run-id'],
      ['get', '/api/admin/scheduler/status'],
      ['get', '/api/admin/health'],
      ['post', '/api/admin/fetch/trigger'],
      ['post', '/api/admin/fetch/retry/some-run-id'],
    ];

    it.each(guarded)(
      '%s %s returns 401 with the Flask body when unauthenticated',
      async (method, path) => {
        const res = await (method === 'post'
          ? server().post(path)
          : server().get(path));
        expect(res.status).toBe(401);
        expect(res.body).toEqual(UNAUTHORIZED);
      },
    );

    it('rejects a garbage bearer token', async () => {
      const res = await server()
        .get('/api/admin/auth/me')
        .set('Authorization', 'Bearer admin:9999999999.deadbeef');
      expect(res.status).toBe(401);
      expect(res.body).toEqual(UNAUTHORIZED);
    });

    it('rejects a garbage X-Admin-Token', async () => {
      const res = await server()
        .get('/api/admin/auth/me')
        .set('X-Admin-Token', 'nonsense');
      expect(res.status).toBe(401);
      expect(res.body).toEqual(UNAUTHORIZED);
    });
  });

  describe('auth routes', () => {
    it('POST /api/admin/auth/logout is public and returns ok', async () => {
      const res = await server().post('/api/admin/auth/logout').expect(200);
      expect(res.body).toEqual({ status: 'ok' });
    });

    it('POST /api/admin/auth/login rejects bad credentials', async () => {
      const res = await server()
        .post('/api/admin/auth/login')
        .send({ username: 'nobody@example.com', password: 'definitely-wrong' });
      // 403 when admin auth is configured, 503 when it is not.
      expect([403, 503]).toContain(res.status);
      if (res.status === 403) {
        expect(res.body).toEqual({
          error: 'Invalid credentials',
          status: 'forbidden',
        });
      } else {
        expect(res.body.status).toBe('disabled');
      }
    });

    const password = process.env.ADMIN_PASSWORD || '';
    const maybe = password ? it : it.skip;

    maybe(
      'issues a token that unlocks the guarded read endpoints',
      async () => {
        const login = await server()
          .post('/api/admin/auth/login')
          .send({
            username: process.env.ADMIN_USERNAME || '',
            password,
          })
          .expect(200);

        expect(login.body.status).toBe('ok');
        expect(login.body.token_type).toBe('Bearer');
        expect(typeof login.body.expires_at).toBe('number');
        expect(String(login.body.token)).toMatch(/^admin:\d+\.[0-9a-f]{64}$/);

        const token = String(login.body.token);

        const me = await server()
          .get('/api/admin/auth/me')
          .set('Authorization', `Bearer ${token}`)
          .expect(200);
        expect(me.body).toEqual({ status: 'ok', role: 'admin' });

        // X-Admin-Token must work identically (Flask accepts either header).
        await server()
          .get('/api/admin/auth/me')
          .set('X-Admin-Token', token)
          .expect(200);

        const status = await server()
          .get('/api/admin/fetch/status')
          .set('Authorization', `Bearer ${token}`)
          .expect(200);
        for (const key of [
          'headline',
          'scheduler',
          'lock',
          'interval_hours',
          'delay_tolerance_minutes',
          'freshness',
          'stats',
          'alerts',
          'pipeline_on_api',
          'admin_token_configured',
        ]) {
          expect(status.body).toHaveProperty(key);
        }
        expect(status.body.pipeline_on_api).toBe(false);

        const history = await server()
          .get('/api/admin/fetch/history?limit=5')
          .set('Authorization', `Bearer ${token}`)
          .expect(200);
        expect(Array.isArray(history.body.runs)).toBe(true);
        expect(history.body.runs.length).toBeLessThanOrEqual(5);
        expect(history.body.count).toBe(history.body.runs.length);
        expect(history.body.stats).toHaveProperty('total');

        const scheduler = await server()
          .get('/api/admin/scheduler/status')
          .set('Authorization', `Bearer ${token}`)
          .expect(200);
        expect(Object.keys(scheduler.body).sort()).toEqual(
          [
            'delay_seconds',
            'delay_tolerance_minutes',
            'headline',
            'interval_hours',
            'last_success',
            'next_run',
            'pipeline_on_api',
            'scheduler',
            'scheduler_delayed',
          ].sort(),
        );

        const health = await server()
          .get('/api/admin/health')
          .set('Authorization', `Bearer ${token}`);
        expect([200, 500]).toContain(health.status);
        expect(health.body).toHaveProperty('checks');

        const missing = await server()
          .get('/api/admin/fetch/definitely-not-a-run-id')
          .set('Authorization', `Bearer ${token}`)
          .expect(404);
        expect(missing.body).toEqual({ error: 'Run not found' });
      },
      30000,
    );
  });

  describe('pipeline routes', () => {
    it('GET /api/pipeline/health returns the sanitized snapshot', async () => {
      const res = await server().get('/api/pipeline/health');
      expect([200, 500]).toContain(res.status);
      if (res.status === 200) {
        expect(res.body).toHaveProperty('scheduler');
        expect(res.body).toHaveProperty('status');
        expect(res.body).toHaveProperty('sources');
        expect(res.body).toHaveProperty('lock');
        // Never leak connection strings or stack traces.
        expect(JSON.stringify(res.body)).not.toMatch(/mongodb(\+srv)?:\/\//);
      }
    });

    it('POST /api/pipeline/run-now refuses a missing/invalid token', async () => {
      const res = await server()
        .post('/api/pipeline/run-now')
        .set('X-Pipeline-Admin-Token', 'not-the-real-token');
      // 403 when a token is configured, 503 when none is configured.
      expect([403, 503]).toContain(res.status);
      if (res.status === 403) {
        expect(res.body).toEqual({
          status: 'forbidden',
          error: 'Invalid admin token',
        });
      }
    });

    it('POST /api/pipeline/run-now refuses when no token header is sent', async () => {
      const res = await server().post('/api/pipeline/run-now');
      expect([403, 503]).toContain(res.status);
    });
  });

  describe('Phase 1-2 endpoints stay intact', () => {
    it('GET /api/health still returns { status, mongo }', async () => {
      const res = await server().get('/api/health').expect(200);
      expect(res.body.status).toBe('ok');
      expect(typeof res.body.mongo).toBe('boolean');
    });

    it('GET /api/news still returns the articles contract', async () => {
      const res = await server().get('/api/news').expect(200);
      expect(Array.isArray(res.body.articles)).toBe(true);
      expect(res.headers['cache-control']).toMatch(/no-store/i);
    });

    it('GET /api/notifications/status still responds', async () => {
      const res = await server().get('/api/notifications/status').expect(200);
      expect(res.body.email).toBeDefined();
      expect(res.body.whatsapp).toBeDefined();
    });
  });
});
