import {
  Injectable,
  Logger,
  OnModuleDestroy,
  OnModuleInit,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Pool } from 'pg';
import { PgDocumentCollection } from './pg-collection';

function safeError(err: unknown): string {
  return String(err instanceof Error ? err.message : err).replace(
    /postgres(?:ql)?:\/\/\S+/gi,
    'postgresql://***',
  );
}

@Injectable()
export class DatabaseService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(DatabaseService.name);
  private pool: Pool | null = null;
  private connected = false;
  private connectPromise: Promise<void> | null = null;
  private readonly gates = new Map<string, Promise<unknown>>();

  constructor(private readonly config: ConfigService) {}

  async onModuleInit(): Promise<void> {
    try {
      await this.connect();
    } catch (err) {
      this.logger.warn('Neon initial connect failed; will retry on health/data access');
      this.logger.debug(safeError(err));
      this.connected = false;
    }
  }

  async onModuleDestroy(): Promise<void> {
    await this.close();
  }

  get isConnected(): boolean {
    return this.connected;
  }

  get dbName(): string {
    return this.config.get<string>('database.name') || 'neondb';
  }

  get articlesCollectionName(): string {
    return this.config.get<string>('database.articlesCollection') || 'articles';
  }

  async connect(): Promise<void> {
    const uri = this.config.get<string>('database.uri') || '';
    if (!uri) {
      this.logger.warn('NEON_DATABASE_URL missing — skipping database connect');
      this.connected = false;
      return;
    }

    if (this.connectPromise) {
      await this.connectPromise;
      return;
    }

    this.connectPromise = (async () => {
      if (!this.pool) {
        this.pool = new Pool({
          connectionString: uri,
          ssl: { rejectUnauthorized: true },
          max: 5,
        });
      }
      await this.pool.query('SELECT 1');
      await this.pool.query('CREATE SCHEMA IF NOT EXISTS mediasphere');
      await this.pool.query(`
        CREATE TABLE IF NOT EXISTS mediasphere.documents (
          collection text NOT NULL,
          doc_id text NOT NULL,
          doc jsonb NOT NULL,
          exported_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (collection, doc_id)
        )
      `);
      this.connected = true;
      this.logger.log('Neon connected (schema=mediasphere)');
    })();

    try {
      await this.connectPromise;
    } catch (err) {
      this.connected = false;
      throw new Error(safeError(err));
    } finally {
      this.connectPromise = null;
    }
  }

  async close(): Promise<void> {
    if (!this.pool) return;
    try {
      await this.pool.end();
    } catch (err) {
      this.logger.warn('Neon close error: ' + safeError(err));
    }
    this.pool = null;
    this.connected = false;
  }

  async ensureConnected(): Promise<boolean> {
    try {
      if (!this.pool) await this.connect();
      else await this.pool.query('SELECT 1');
      this.connected = Boolean(this.pool);
      return this.connected;
    } catch {
      this.connected = false;
      try {
        await this.close();
        await this.connect();
        return this.connected;
      } catch {
        this.connected = false;
        return false;
      }
    }
  }

  collection(name: string): PgDocumentCollection {
    if (!this.pool) throw new Error('Neon database is not initialized');
    return new PgDocumentCollection(this.pool, name, (fn) => this.exclusive(name, fn));
  }

  articles(): PgDocumentCollection {
    return this.collection(this.articlesCollectionName);
  }

  async ping(): Promise<{ ok: boolean; latencyMs: number }> {
    const ok = await this.ensureConnected();
    if (!ok || !this.pool) throw new Error('Neon database unavailable');
    const started = Date.now();
    await this.pool.query('SELECT 1');
    return {
      ok: true,
      latencyMs: Math.round((Date.now() - started) * 100) / 100,
    };
  }

  private exclusive<T>(name: string, fn: () => Promise<T>): Promise<T> {
    const previous = this.gates.get(name) ?? Promise.resolve();
    const run = previous.then(fn, fn);
    this.gates.set(name, run.then(() => undefined, () => undefined));
    return run;
  }
}
