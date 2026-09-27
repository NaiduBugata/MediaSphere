/**
 * One-way copy of MediaSphere MongoDB collections into Neon PostgreSQL.
 * Reads MONGODB_URI and NEON_DATABASE_URL from server/.env. Does not print them.
 * Mongo is only read. Rows land in schema mediasphere, table documents.
 */
import fs from 'node:fs';
import { MongoClient } from 'mongodb';
import { EJSON } from 'bson';
import pg from 'pg';

function loadEnv(file) {
  const text = fs.readFileSync(file, 'utf8');
  const env = {};
  for (const line of text.split(/\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq < 1) continue;
    env[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
  }
  return env;
}

function safeError(err) {
  return String(err && err.message ? err.message : err).replace(
    /postgres(?:ql)?:\/\/\S+/gi,
    'postgresql://***',
  );
}

function docId(doc) {
  if (doc._id == null) return '';
  if (typeof doc._id === 'object' && doc._id.toHexString) return doc._id.toHexString();
  return String(doc._id);
}

const env = loadEnv(new URL('../.env', import.meta.url));
if (!env.MONGODB_URI || !env.NEON_DATABASE_URL) {
  console.error('MONGODB_URI and NEON_DATABASE_URL must both be set in server/.env');
  process.exit(1);
}

const mongo = new MongoClient(env.MONGODB_URI);
const sql = new pg.Client({
  connectionString: env.NEON_DATABASE_URL,
  ssl: { rejectUnauthorized: true },
});

const counts = [];
try {
  await mongo.connect();
  await sql.connect();
  const db = mongo.db(env.MONGODB_DB_NAME || 'MediaSphere');
  const names = (await db.listCollections().toArray())
    .map((item) => item.name)
    .filter((name) => !name.startsWith('system.'))
    .sort();

  await sql.query('BEGIN');
  await sql.query('CREATE SCHEMA IF NOT EXISTS mediasphere');
  await sql.query(`
    CREATE TABLE IF NOT EXISTS mediasphere.documents (
      collection text NOT NULL,
      doc_id text NOT NULL,
      doc jsonb NOT NULL,
      exported_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (collection, doc_id)
    )
  `);
  await sql.query('DELETE FROM mediasphere.documents');

  for (const name of names) {
    const docs = await db.collection(name).find({}).toArray();
    for (let i = 0; i < docs.length; i += 100) {
      const chunk = docs.slice(i, i + 100);
      const values = [];
      const params = [];
      chunk.forEach((doc, index) => {
        const base = index * 3;
        values.push(`($${base + 1}, $${base + 2}, $${base + 3}::jsonb)`);
        params.push(name, docId(doc), EJSON.stringify(doc));
      });
      await sql.query(
        `INSERT INTO mediasphere.documents (collection, doc_id, doc) VALUES ${values.join(', ')}`,
        params,
      );
    }
    counts.push({ collection: name, mongo: docs.length });
  }

  await sql.query('COMMIT');

  const check = await sql.query(
    'SELECT collection, count(*)::int AS n FROM mediasphere.documents GROUP BY collection ORDER BY collection',
  );
  const neon = new Map(check.rows.map((row) => [row.collection, row.n]));
  let mismatch = false;
  for (const row of counts) {
    const copied = neon.get(row.collection) ?? 0;
    const ok = copied === row.mongo;
    if (!ok) mismatch = true;
    console.log(`${row.collection} mongo=${row.mongo} neon=${copied} ${ok ? 'ok' : 'MISMATCH'}`);
  }
  console.log(`collections=${counts.length} neon_rows=${check.rows.reduce((sum, row) => sum + row.n, 0)}`);
  if (mismatch) process.exitCode = 1;
} catch (err) {
  try {
    await sql.query('ROLLBACK');
  } catch {
    /* connection may not be open */
  }
  console.error(safeError(err));
  process.exitCode = 1;
} finally {
  await sql.end().catch(() => {});
  await mongo.close().catch(() => {});
}
