import { BadRequestException, Injectable, NotFoundException, ServiceUnavailableException } from '@nestjs/common';
import { randomBytes } from 'node:crypto';
import { DatabaseService } from '../database/database.service';

/** Shared with the WhatsApp chatbot, which lists the same records under "Visits". */
const RECORDS = 'jv_records';
const SECTION = 'visits';

export type VisitFileKind = 'pdf' | 'word' | 'excel';

const TYPES: Record<string, { kind: VisitFileKind; mime: string; magic: 'pdf' | 'zip' | 'ole' }> = {
  pdf: { kind: 'pdf', mime: 'application/pdf', magic: 'pdf' },
  doc: { kind: 'word', mime: 'application/msword', magic: 'ole' },
  docx: { kind: 'word', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', magic: 'zip' },
  xls: { kind: 'excel', mime: 'application/vnd.ms-excel', magic: 'ole' },
  xlsx: { kind: 'excel', mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', magic: 'zip' },
};

const KIND_LABEL: Record<VisitFileKind, string> = { pdf: 'PDF', word: 'Word', excel: 'Excel' };

export const VISIT_EXTENSIONS = Object.keys(TYPES);

export interface UploadedVisitFile {
  originalname: string;
  size: number;
  buffer: Buffer;
}

export interface VisitInput {
  title: string;
  place?: string;
  visitDate?: string;
  detail?: string;
}

export interface Visit {
  id: string;
  title: string;
  place: string;
  visitDate: string;
  detail: string;
  createdAt: string;
  file: { id: string; name: string; kind: VisitFileKind; size: number } | null;
}

export function maxUploadBytes(env: NodeJS.ProcessEnv = process.env): number {
  const mb = Number(env.VISITS_MAX_UPLOAD_MB || '10');
  return Math.round((Number.isFinite(mb) && mb > 0 ? mb : 10) * 1024 * 1024);
}

/** Extension and file signature must agree, so a renamed executable or image is refused. */
export function detectVisitFile(name: string, buffer: Buffer): { ext: string; kind: VisitFileKind; mime: string } {
  const ext = (name.split('.').pop() || '').toLowerCase();
  const type = TYPES[ext];
  if (!type || !name.includes('.')) {
    throw new BadRequestException('Only PDF, Word (.doc, .docx), or Excel (.xls, .xlsx) files can be uploaded.');
  }
  const head = buffer.subarray(0, 8);
  const signature = {
    pdf: head.subarray(0, 5).toString('latin1') === '%PDF-',
    zip: head[0] === 0x50 && head[1] === 0x4b && head[2] === 0x03 && head[3] === 0x04,
    ole: head.equals(Buffer.from([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1])),
  };
  if (!signature[type.magic]) {
    throw new BadRequestException(`The file is not a valid .${ext} document.`);
  }
  return { ext, kind: type.kind, mime: type.mime };
}

export function safeFileName(name: string): string {
  const base = name.split(/[\\/]/).pop() || 'file';
  const cleaned = base.replace(/[\u0000-\u001f"<>:|?*]+/g, '_').replace(/\s+/g, ' ').trim();
  return (cleaned || 'file').slice(0, 150);
}

function text(value: unknown, max: number): string {
  return typeof value === 'string' ? value.trim().slice(0, max) : '';
}

function isoDay(value: string | undefined): string {
  const day = (value || '').trim();
  if (!day) return '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || Number.isNaN(Date.parse(day))) {
    throw new BadRequestException('Visit date must be a date like 2026-09-29.');
  }
  return day;
}

@Injectable()
export class VisitsService {
  private tableReady = false;

  constructor(private readonly db: DatabaseService) {}

  async list(): Promise<Visit[]> {
    await this.ready();
    const rows = await this.db.collection(RECORDS).find({ section: SECTION }).toArray();
    return rows.map(toVisit).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
  }

  async create(input: VisitInput, file: UploadedVisitFile | undefined): Promise<Visit> {
    if (!file || !file.buffer?.length) throw new BadRequestException('Choose a PDF, Word, or Excel file to upload.');
    if (file.size > maxUploadBytes()) {
      throw new BadRequestException(`The file is larger than ${Math.round(maxUploadBytes() / 1024 / 1024)} MB.`);
    }
    const title = text(input.title, 200);
    if (!title) throw new BadRequestException('Title is required.');
    const visitDate = isoDay(input.visitDate);
    const detected = detectVisitFile(file.originalname || '', file.buffer);
    const name = safeFileName(file.originalname);
    await this.ready();

    const fileId = randomBytes(12).toString('hex');
    await this.db.query(
      'INSERT INTO mediasphere.visit_files (id, name, mime, size, data) VALUES ($1, $2, $3, $4, $5)',
      [fileId, name, detected.mime, file.buffer.length, file.buffer],
    );
    const createdAt = new Date().toISOString();
    const doc = {
      section: SECTION,
      title,
      place: text(input.place, 120),
      visitDate,
      detail: text(input.detail, 2000),
      status: KIND_LABEL[detected.kind],
      file: { id: fileId, name, kind: detected.kind, size: file.buffer.length },
      createdAt,
      createdBy: 'admin',
    };
    try {
      const inserted = await this.db.collection(RECORDS).insertOne(doc);
      return toVisit({ ...doc, _id: inserted.insertedId });
    } catch (err) {
      await this.db.query('DELETE FROM mediasphere.visit_files WHERE id = $1', [fileId]).catch(() => undefined);
      throw err;
    }
  }

  async file(id: string): Promise<{ name: string; mime: string; data: Buffer }> {
    if (!/^[a-f0-9]{24}$/.test(id)) throw new NotFoundException('File not found');
    await this.ready();
    const rows = await this.db.query<{ name: string; mime: string; data: Buffer }>(
      'SELECT name, mime, data FROM mediasphere.visit_files WHERE id = $1',
      [id],
    );
    if (!rows.length) throw new NotFoundException('File not found');
    return rows[0];
  }

  async remove(id: string): Promise<void> {
    await this.ready();
    const coll = this.db.collection(RECORDS);
    const doc = (await coll.find({ section: SECTION }).toArray()).find((row) => String(row._id) === id);
    if (!doc) throw new NotFoundException('Visit not found');
    await coll.deleteOne({ _id: doc._id });
    const fileId = (doc.file as { id?: string } | undefined)?.id;
    if (fileId) await this.db.query('DELETE FROM mediasphere.visit_files WHERE id = $1', [fileId]);
  }

  private async ready(): Promise<void> {
    const ok = await this.db.ensureConnected();
    if (!ok) throw new ServiceUnavailableException('Database is not connected');
    if (this.tableReady) return;
    await this.db.query(`
      CREATE TABLE IF NOT EXISTS mediasphere.visit_files (
        id text PRIMARY KEY,
        name text NOT NULL,
        mime text NOT NULL,
        size integer NOT NULL,
        data bytea NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      )
    `);
    this.tableReady = true;
  }
}

function sortKey(visit: Visit): string {
  return `${visit.visitDate || visit.createdAt.slice(0, 10)}|${visit.createdAt}`;
}

function toVisit(doc: Record<string, unknown>): Visit {
  const file = (doc.file || {}) as Record<string, unknown>;
  const kind = (['pdf', 'word', 'excel'].includes(String(file.kind)) ? file.kind : 'pdf') as VisitFileKind;
  return {
    id: String(doc._id),
    title: String(doc.title || ''),
    place: String(doc.place || ''),
    visitDate: String(doc.visitDate || ''),
    detail: String(doc.detail || ''),
    createdAt: String(doc.createdAt || ''),
    file: file.id
      ? { id: String(file.id), name: String(file.name || ''), kind, size: Number(file.size || 0) }
      : null,
  };
}
