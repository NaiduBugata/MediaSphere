import { ConflictException, Injectable, ServiceUnavailableException, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createHmac, randomBytes, scryptSync, timingSafeEqual } from 'node:crypto';
import { ObjectId } from 'mongodb';
import { DatabaseService } from '../database/database.service';
import { WORKSPACE_SECTIONS, type WorkspaceSection } from './workspace.dto';

const USERS = 'jv_users';
const RECORDS = 'jv_records';

export interface WorkspaceUser {
  id: string;
  email: string;
  name: string;
}

export interface WorkspaceRecord {
  id: string;
  section: WorkspaceSection;
  title: string;
  detail: string;
  status: string;
  date: string;
  createdBy: string;
}

@Injectable()
export class WorkspaceService {
  constructor(
    private readonly db: DatabaseService,
    private readonly config: ConfigService,
  ) {}

  async register(email: string, password: string, name?: string): Promise<{ token: string; user: WorkspaceUser }> {
    await this.ready();
    const normalized = email.trim().toLowerCase();
    const existing = await this.db.collection(USERS).findOne({ email: normalized });
    if (existing) throw new ConflictException('An account with this email already exists');
    const display = (name || normalized.split('@')[0]).trim();
    const inserted = await this.db.collection(USERS).insertOne({
      email: normalized,
      name: display,
      passwordHash: hashPassword(password),
      createdAt: new Date().toISOString(),
    });
    const user = { id: String(inserted.insertedId), email: normalized, name: display };
    return { token: this.sign(user.id), user };
  }

  async login(email: string, password: string): Promise<{ token: string; user: WorkspaceUser }> {
    await this.ready();
    const normalized = email.trim().toLowerCase();
    const doc = await this.db.collection(USERS).findOne({ email: normalized });
    if (!doc || !verifyPassword(password, String(doc.passwordHash || ''))) {
      throw new UnauthorizedException('Email or password is incorrect');
    }
    const user = { id: String(doc._id), email: normalized, name: String(doc.name || normalized.split('@')[0]) };
    return { token: this.sign(user.id), user };
  }

  async me(token: string): Promise<WorkspaceUser> {
    const id = this.verify(token);
    await this.ready();
    const doc = await this.db.collection(USERS).findOne({ _id: asId(id) as never });
    if (!doc) throw new UnauthorizedException('Session expired');
    return { id, email: String(doc.email), name: String(doc.name || '') };
  }

  async list(section: WorkspaceSection): Promise<WorkspaceRecord[]> {
    await this.ready();
    const rows = await this.db.collection(RECORDS).find({ section }).sort({ createdAt: -1 }).limit(200).toArray();
    return rows.map(toRecord);
  }

  async create(input: { section: WorkspaceSection; title: string; detail?: string; status?: string; createdBy: string }): Promise<WorkspaceRecord> {
    await this.ready();
    const createdAt = new Date().toISOString();
    const doc = {
      section: input.section,
      title: input.title.trim(),
      detail: (input.detail || '').trim(),
      status: (input.status || 'Open').trim() || 'Open',
      createdAt,
      createdBy: input.createdBy,
    };
    const inserted = await this.db.collection(RECORDS).insertOne(doc);
    return toRecord({ ...doc, _id: inserted.insertedId });
  }

  async summary(): Promise<{
    counts: Record<WorkspaceSection, number>;
    open: number;
    news: number;
    mongo: boolean;
  }> {
    await this.ready();
    const counts = {} as Record<WorkspaceSection, number>;
    for (const section of WORKSPACE_SECTIONS) {
      counts[section] = await this.db.collection(RECORDS).countDocuments({ section });
    }
    const open = await this.db.collection(RECORDS).countDocuments({ status: { $in: ['Open', 'In progress'] } });
    let news = 0;
    try {
      news = await this.db.collection(this.db.articlesCollectionName).countDocuments({});
    } catch {
      news = 0;
    }
    return { counts, open, news, mongo: true };
  }

  private async ready(): Promise<void> {
    const ok = await this.db.ensureConnected();
    if (!ok) throw new ServiceUnavailableException('Database is not connected');
  }

  private secret(): string {
    return this.config.get<string>('admin.sessionSecret') || 'mediasphere-admin-dev-insecure';
  }

  private sign(userId: string): string {
    const exp = Math.floor(Date.now() / 1000) + 60 * 60 * 12;
    const payload = `${userId}.${exp}`;
    const sig = createHmac('sha256', this.secret()).update(`jv:${payload}`).digest('hex');
    return `${payload}.${sig}`;
  }

  verify(token: string): string {
    const parts = token.split('.');
    if (parts.length !== 3) throw new UnauthorizedException('Session expired');
    const [userId, exp, sig] = parts;
    const expected = createHmac('sha256', this.secret()).update(`jv:${userId}.${exp}`).digest('hex');
    const a = Buffer.from(sig);
    const b = Buffer.from(expected);
    if (a.length !== b.length || !timingSafeEqual(a, b)) throw new UnauthorizedException('Session expired');
    if (Number(exp) < Math.floor(Date.now() / 1000)) throw new UnauthorizedException('Session expired');
    return userId;
  }
}

function hashPassword(password: string): string {
  const salt = randomBytes(16).toString('hex');
  const hash = scryptSync(password, salt, 32).toString('hex');
  return `${salt}:${hash}`;
}

function verifyPassword(password: string, stored: string): boolean {
  const [salt, hash] = stored.split(':');
  if (!salt || !hash) return false;
  const next = scryptSync(password, salt, 32);
  const prev = Buffer.from(hash, 'hex');
  if (next.length !== prev.length) return false;
  return timingSafeEqual(next, prev);
}

function asId(id: string): ObjectId | string {
  return ObjectId.isValid(id) && String(new ObjectId(id)) === id ? new ObjectId(id) : id;
}

function toRecord(doc: Record<string, unknown>): WorkspaceRecord {
  return {
    id: String(doc._id),
    section: doc.section as WorkspaceSection,
    title: String(doc.title || ''),
    detail: String(doc.detail || ''),
    status: String(doc.status || 'Open'),
    date: String(doc.createdAt || ''),
    createdBy: String(doc.createdBy || ''),
  };
}
