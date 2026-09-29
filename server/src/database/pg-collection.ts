import { ObjectId } from 'mongodb';
import type { Pool } from 'pg';

const DATE_FIELDS = new Set(['expires_at', 'acquired_at', 'updated_at', 'released_at']);

export class DuplicateDocumentError extends Error {
  readonly code = 11000;

  constructor() {
    super('duplicate document');
  }
}

type Filter = Record<string, unknown>;
type Doc = Record<string, unknown>;

function isOperator(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  if (value instanceof Date || isObjectId(value)) return false;
  return Object.keys(value).some((key) => key.startsWith('$'));
}

function isObjectId(value: unknown): value is ObjectId {
  return Boolean(value && typeof value === 'object' && typeof (value as ObjectId).toHexString === 'function');
}

function idKey(value: unknown): string | null {
  if (isObjectId(value)) return value.toHexString();
  if (typeof value === 'string' && /^[a-f0-9]{24}$/i.test(value)) return value.toLowerCase();
  return null;
}

function same(actual: unknown, expected: unknown): boolean {
  if (actual === expected) return true;
  const left = idKey(actual);
  const right = idKey(expected);
  if (left && right) return left === right;
  const leftTime = timeOf(actual);
  const rightTime = timeOf(expected);
  if (leftTime != null && rightTime != null) return leftTime === rightTime;
  return false;
}

function timeOf(value: unknown): number | null {
  if (value instanceof Date) return value.getTime();
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    const parsed = Date.parse(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
}

function compare(actual: unknown, expected: unknown): number {
  const leftTime = timeOf(actual);
  const rightTime = timeOf(expected);
  if (leftTime != null && rightTime != null) return leftTime - rightTime;
  const left = actual == null ? '' : String(actual);
  const right = expected == null ? '' : String(expected);
  if (left < right) return -1;
  if (left > right) return 1;
  return 0;
}

function matchValue(actual: unknown, expected: unknown): boolean {
  if (isOperator(expected)) {
    if ('$in' in expected) {
      const list = expected.$in;
      return Array.isArray(list) && list.some((item) => same(actual, item));
    }
    if ('$lte' in expected) return compare(actual, expected.$lte) <= 0;
    if ('$exists' in expected) {
      const exists = actual !== undefined;
      return expected.$exists ? exists : !exists;
    }
    return false;
  }
  if (expected === null) return actual == null;
  return same(actual, expected);
}

export function matches(doc: Doc, filter: Filter | undefined): boolean {
  if (!filter) return true;
  const entries = Object.entries(filter);
  if (!entries.length) return true;
  for (const [key, expected] of entries) {
    if (key === '$or') {
      const clauses = Array.isArray(expected) ? expected : [];
      if (!clauses.some((clause) => matches(doc, clause as Filter))) return false;
      continue;
    }
    if (!matchValue(doc[key], expected)) return false;
  }
  return true;
}

function equalityFields(filter: Filter): Doc {
  const doc: Doc = {};
  for (const [key, value] of Object.entries(filter)) {
    if (key.startsWith('$') || isOperator(value)) continue;
    doc[key] = value;
  }
  return doc;
}

function hydrate(raw: unknown): Doc {
  const doc = revive(raw) as Doc;
  for (const key of DATE_FIELDS) {
    const value = doc[key];
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
      const date = new Date(value);
      if (!Number.isNaN(date.getTime())) doc[key] = date;
    }
  }
  return doc;
}

function revive(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(revive);
  if (!value || typeof value !== 'object') return value;
  const record = value as Doc;
  if (typeof record.$oid === 'string' && Object.keys(record).length === 1) {
    return new ObjectId(record.$oid);
  }
  if (typeof record.$date === 'string' && Object.keys(record).length === 1) {
    return new Date(record.$date);
  }
  const next: Doc = {};
  for (const [key, item] of Object.entries(record)) next[key] = revive(item);
  return next;
}

function serialize(doc: Doc): string {
  return JSON.stringify(toJson(doc));
}

function toJson(value: unknown): unknown {
  if (value instanceof Date) return { $date: value.toISOString() };
  if (isObjectId(value)) return { $oid: value.toHexString() };
  if (Array.isArray(value)) return value.map(toJson);
  if (value && typeof value === 'object') {
    const next: Doc = {};
    for (const [key, item] of Object.entries(value as Doc)) next[key] = toJson(item);
    return next;
  }
  return value;
}

function docId(doc: Doc): string {
  if (doc._id == null) doc._id = new ObjectId();
  if (isObjectId(doc._id)) return doc._id.toHexString();
  return String(doc._id);
}

function project(doc: Doc, projection?: Record<string, number>): Doc {
  if (!projection) return doc;
  const include = Object.entries(projection).filter(([, flag]) => flag);
  if (!include.length) return doc;
  const next: Doc = {};
  if (projection._id !== 0 && doc._id !== undefined) next._id = doc._id;
  for (const [key, flag] of include) {
    if (key === '_id' || !flag) continue;
    if (key in doc) next[key] = doc[key];
  }
  return next;
}

class QueryCursor {
  private sortSpec: Record<string, number> | null = null;
  private max: number | null = null;

  constructor(
    private readonly load: () => Promise<Doc[]>,
    private readonly filter: Filter,
  ) {}

  sort(spec: Record<string, number>): this {
    this.sortSpec = spec;
    return this;
  }

  limit(count: number): this {
    this.max = count;
    return this;
  }

  async toArray(): Promise<Doc[]> {
    let rows = (await this.load()).filter((doc) => matches(doc, this.filter));
    if (this.sortSpec) {
      const [field, direction] = Object.entries(this.sortSpec)[0] || [];
      if (field) {
        const sign = direction < 0 ? -1 : 1;
        rows.sort((a, b) => sign * compare(a[field], b[field]));
      }
    }
    if (this.max != null) rows = rows.slice(0, this.max);
    return rows;
  }
}

/** Document collection stored as JSON rows in Neon (`mediasphere.documents`). */
export class PgDocumentCollection {
  constructor(
    private readonly pool: Pool,
    private readonly name: string,
    private readonly exclusive: <T>(fn: () => Promise<T>) => Promise<T>,
  ) {}

  private async load(): Promise<Doc[]> {
    const result = await this.pool.query(
      'SELECT doc_id, doc FROM mediasphere.documents WHERE collection = $1',
      [this.name],
    );
    return result.rows.map((row: { doc: unknown }) => hydrate(row.doc));
  }

  find(filter: Filter = {}): QueryCursor {
    return new QueryCursor(() => this.exclusive(() => this.load()), filter);
  }

  async findOne(filter: Filter = {}, options?: { sort?: Record<string, number>; projection?: Record<string, number> }): Promise<Doc | null> {
    return this.exclusive(async () => {
      let rows = (await this.load()).filter((doc) => matches(doc, filter));
      if (options?.sort) {
        const [field, direction] = Object.entries(options.sort)[0] || [];
        if (field) {
          const sign = direction < 0 ? -1 : 1;
          rows.sort((a, b) => sign * compare(a[field], b[field]));
        }
      }
      const doc = rows[0];
      return doc ? project(doc, options?.projection) : null;
    });
  }

  async countDocuments(filter: Filter = {}): Promise<number> {
    return this.exclusive(async () => (await this.load()).filter((doc) => matches(doc, filter)).length);
  }

  async insertOne(doc: Doc): Promise<{ insertedId: unknown }> {
    return this.exclusive(async () => {
      const stored = { ...doc };
      const id = docId(stored);
      const existing = await this.pool.query(
        'SELECT 1 FROM mediasphere.documents WHERE collection = $1 AND doc_id = $2',
        [this.name, id],
      );
      if (existing.rowCount) throw new DuplicateDocumentError();
      await this.pool.query(
        `INSERT INTO mediasphere.documents (collection, doc_id, doc)
         VALUES ($1, $2, $3::jsonb)`,
        [this.name, id, serialize(stored)],
      );
      return { insertedId: stored._id };
    });
  }

  /** New documents only: every `_id` is freshly generated, so there is no duplicate check. */
  async insertMany(docs: Doc[]): Promise<{ insertedIds: unknown[] }> {
    if (!docs.length) return { insertedIds: [] };
    return this.exclusive(async () => {
      const stored = docs.map((doc) => {
        const copy = { ...doc };
        delete copy._id;
        return copy;
      });
      const ids = stored.map((doc) => docId(doc));
      await this.pool.query(
        `INSERT INTO mediasphere.documents (collection, doc_id, doc)
         SELECT $1, t.id, t.doc::jsonb FROM unnest($2::text[], $3::text[]) AS t(id, doc)`,
        [this.name, ids, stored.map(serialize)],
      );
      return { insertedIds: stored.map((doc) => doc._id) };
    });
  }

  async updateOne(
    filter: Filter,
    update: { $set?: Doc; $setOnInsert?: Doc },
    options?: { upsert?: boolean },
  ): Promise<{ matchedCount: number; modifiedCount: number; upsertedCount: number; upsertedId: unknown }> {
    return this.exclusive(async () => {
      const rows = await this.load();
      const hit = rows.find((doc) => matches(doc, filter));
      if (hit) {
        Object.assign(hit, update.$set || {});
        await this.write(hit);
        return { matchedCount: 1, modifiedCount: 1, upsertedCount: 0, upsertedId: null };
      }
      if (!options?.upsert) {
        return { matchedCount: 0, modifiedCount: 0, upsertedCount: 0, upsertedId: null };
      }
      const created: Doc = {
        ...equalityFields(filter),
        ...(update.$setOnInsert || {}),
        ...(update.$set || {}),
      };
      docId(created);
      await this.write(created);
      return { matchedCount: 0, modifiedCount: 0, upsertedCount: 1, upsertedId: created._id };
    });
  }

  async findOneAndUpdate(
    filter: Filter,
    update: { $set?: Doc },
    _options?: { returnDocument?: string },
  ): Promise<Doc | null> {
    return this.exclusive(async () => {
      const hit = (await this.load()).find((doc) => matches(doc, filter));
      if (!hit) return null;
      Object.assign(hit, update.$set || {});
      await this.write(hit);
      return hit;
    });
  }

  async deleteOne(filter: Filter): Promise<{ deletedCount: number }> {
    return this.exclusive(async () => {
      const hit = (await this.load()).find((doc) => matches(doc, filter));
      if (!hit) return { deletedCount: 0 };
      const result = await this.pool.query(
        'DELETE FROM mediasphere.documents WHERE collection = $1 AND doc_id = $2',
        [this.name, docId(hit)],
      );
      return { deletedCount: result.rowCount || 0 };
    });
  }

  async createIndex(_keys: Record<string, number>): Promise<string> {
    return 'ok';
  }

  private async write(doc: Doc): Promise<void> {
    const id = docId(doc);
    await this.pool.query(
      `INSERT INTO mediasphere.documents (collection, doc_id, doc)
       VALUES ($1, $2, $3::jsonb)
       ON CONFLICT (collection, doc_id) DO UPDATE
       SET doc = EXCLUDED.doc, exported_at = now()`,
      [this.name, id, serialize(doc)],
    );
  }
}
