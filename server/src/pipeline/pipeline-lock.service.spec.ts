import { ConfigService } from '@nestjs/config';
import { PipelineLockService } from './pipeline-lock.service';
import { DatabaseService } from '../database/database.service';

/**
 * Minimal in-memory stand-in for the `pipeline_lock` collection that reproduces
 * the two behaviours the lock relies on: a conditional findOneAndUpdate and a
 * unique `_id` (duplicate key error 11000) on insert.
 */
class FakeLockCollection {
  docs = new Map<string, Record<string, unknown>>();
  createIndex = jest.fn().mockResolvedValue('expires_at_1');

  private matches(
    doc: Record<string, unknown> | undefined,
    filter: Record<string, any>,
  ): boolean {
    if (!doc) return false;
    if (filter.owner !== undefined && doc.owner !== filter.owner) return false;
    if (!filter.$or) return true;
    return filter.$or.some((clause: Record<string, any>) => {
      if (clause.owner && clause.owner.$exists === false) {
        return !('owner' in doc);
      }
      if ('owner' in clause && clause.owner === null) return doc.owner === null;
      if (clause.expires_at && clause.expires_at.$lte) {
        return (
          doc.expires_at instanceof Date &&
          doc.expires_at <= clause.expires_at.$lte
        );
      }
      return false;
    });
  }

  findOneAndUpdate(
    filter: Record<string, any>,
    update: { $set: Record<string, unknown> },
  ) {
    const key = String(filter._id);
    const doc = this.docs.get(key);
    if (!this.matches(doc, filter)) return Promise.resolve(null);
    const next = { ...doc, ...update.$set };
    this.docs.set(key, next);
    return Promise.resolve(next);
  }

  insertOne(doc: Record<string, unknown>) {
    const key = String(doc._id);
    if (this.docs.has(key)) {
      return Promise.reject(
        Object.assign(new Error('E11000'), { code: 11000 }),
      );
    }
    this.docs.set(key, { ...doc });
    return Promise.resolve({ insertedId: doc._id });
  }

  updateOne(
    filter: Record<string, any>,
    update: { $set: Record<string, unknown> },
  ) {
    const key = String(filter._id);
    const doc = this.docs.get(key);
    if (!this.matches(doc, filter))
      return Promise.resolve({ modifiedCount: 0 });
    this.docs.set(key, { ...doc, ...update.$set });
    return Promise.resolve({ modifiedCount: 1 });
  }

  findOne(filter: Record<string, any>) {
    return Promise.resolve(this.docs.get(String(filter._id)) || null);
  }
}

function makeLock(): { lock: PipelineLockService; coll: FakeLockCollection } {
  const coll = new FakeLockCollection();
  const db = {
    ensureConnected: jest.fn().mockResolvedValue(true),
    collection: () => coll,
  } as unknown as DatabaseService;
  const values: Record<string, unknown> = {
    'pipeline.stateId': 'pipeline',
    'pipeline.lockTtlSeconds': 2700,
  };
  const config = { get: (k: string) => values[k] } as unknown as ConfigService;
  return { lock: new PipelineLockService(db, config), coll };
}

describe('PipelineLockService (MongoDB atomic lock)', () => {
  it('acquires when no lock document exists', async () => {
    const { lock } = makeLock();
    const owner = await lock.acquire();
    expect(owner).toBeTruthy();
    expect(owner).toMatch(/:[0-9a-f]{12}$/);
  });

  it('denies a second acquire while the lock is live', async () => {
    const { lock } = makeLock();
    const first = await lock.acquire('owner-a');
    const second = await lock.acquire('owner-b');
    expect(first).toBe('owner-a');
    expect(second).toBeNull();
  });

  it('denies concurrent acquires — exactly one winner', async () => {
    const { lock } = makeLock();
    const results = await Promise.all([
      lock.acquire('a'),
      lock.acquire('b'),
      lock.acquire('c'),
      lock.acquire('d'),
    ]);
    expect(results.filter(Boolean)).toHaveLength(1);
  });

  it('re-acquires after the owner releases', async () => {
    const { lock } = makeLock();
    const first = await lock.acquire('owner-a');
    expect(await lock.release(first as string)).toBe(true);
    expect(await lock.acquire('owner-b')).toBe('owner-b');
  });

  it('refuses to release a lock owned by someone else', async () => {
    const { lock } = makeLock();
    await lock.acquire('owner-a');
    expect(await lock.release('owner-b')).toBe(false);
    expect(await lock.acquire('owner-c')).toBeNull();
  });

  it('takes over a stale lock once expires_at has passed', async () => {
    const { lock, coll } = makeLock();
    await lock.acquire('dead-owner');
    const doc = coll.docs.get('pipeline')!;
    doc.expires_at = new Date(Date.now() - 1000);
    expect(await lock.acquire('fresh-owner')).toBe('fresh-owner');
  });

  it('reports held/expiry in Flask lock summary shape', async () => {
    const { lock, coll } = makeLock();
    await lock.acquire('owner-a', 60);
    const held = await lock.summary();
    expect(held.held).toBe(true);
    expect(held.owner_present).toBe(true);
    // pymongo isoformat of a naive UTC datetime — no Z/offset suffix.
    expect(held.expires_at).toMatch(/^\d{4}-\d{2}-\d{2}T[\d:.]+$/);

    await lock.release('owner-a');
    const released = await lock.summary();
    expect(released.held).toBe(false);
    expect(released.owner_present).toBe(false);

    await lock.acquire('owner-b', 60);
    coll.docs.get('pipeline')!.expires_at = new Date(Date.now() - 1);
    expect((await lock.summary()).held).toBe(false);
  });
});
