import { Injectable, Logger } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { whatsappSenderReady } from '../birthdays/birthdays';
import { calendarDay } from '../reports/report-stats';
import { sendTemplateMessage } from '../whatsapp/whatsapp.send';
import { FOLLOW_UP_TEMPLATE, followUpParameters, isAutoDue, listedPhones, type FollowUpVisit } from './visit-followup';

const RECORDS = 'jv_records';
const ZONE = 'Asia/Kolkata';

export interface FollowUpResult {
  due: number;
  sent: number;
  failed: number;
}

interface StoredVisit extends FollowUpVisit {
  rawId: unknown;
}

@Injectable()
export class VisitFollowupService {
  private readonly logger = new Logger(VisitFollowupService.name);

  constructor(private readonly db: DatabaseService) {}

  /** Every lead for visits scheduled today. The MP asked, so this sends even when the morning reminder already went. */
  async sendToday(fetchImpl: typeof fetch = fetch, now = new Date()): Promise<FollowUpResult> {
    const today = calendarDay(now, ZONE);
    const visits = (await this.load()).filter((visit) => visit.visitDate === today && listedPhones(visit).length);
    return this.deliver(visits, fetchImpl, false);
  }

  /** Every saved visit, every tap. Nothing is marked, so Follow up can be sent again. */
  async sendAll(fetchImpl: typeof fetch = fetch): Promise<FollowUpResult> {
    const visits = (await this.load()).filter((visit) => listedPhones(visit).length);
    return this.deliver(visits, fetchImpl, false);
  }

  /** One automatic reminder per visit: 7:00 AM, or 3 hours before a visit that is earlier than 7:00 AM. */
  async sendDue(fetchImpl: typeof fetch = fetch, now = new Date()): Promise<FollowUpResult> {
    const due = (await this.load()).filter((visit) => isAutoDue(visit, now));
    return this.deliver(due, fetchImpl, true);
  }

  private async deliver(visits: StoredVisit[], fetchImpl: typeof fetch, mark: boolean): Promise<FollowUpResult> {
    const jobs = visits.flatMap((visit) => listedPhones(visit).map((phone) => ({ visit, phone })));
    if (!jobs.length || !whatsappSenderReady()) {
      return { due: jobs.length, sent: 0, failed: jobs.length && !whatsappSenderReady() ? jobs.length : 0 };
    }
    let sent = 0;
    let failed = 0;
    const failedIds = new Set<string>();
    for (const job of jobs) {
      try {
        await sendTemplateMessage(job.phone, FOLLOW_UP_TEMPLATE, {
          language: 'en',
          namedParameters: followUpParameters(job.visit),
          fetchImpl,
        });
        sent += 1;
      } catch (err) {
        failed += 1;
        failedIds.add(job.visit.id);
        this.logger.warn(`Visit follow-up was not accepted: ${err instanceof Error ? err.message : 'send failed'}`);
      }
    }
    if (mark) {
      for (const visit of visits) {
        if (!listedPhones(visit).length || failedIds.has(visit.id)) continue;
        await this.markSent(visit);
      }
    }
    return { due: jobs.length, sent, failed };
  }

  private async load(): Promise<StoredVisit[]> {
    if (!(await this.db.ensureConnected())) return [];
    const rows = await this.db.collection(RECORDS).find({ section: 'visits' }).toArray();
    return rows.map((row) => ({
      id: String(row._id),
      rawId: row._id,
      title: String(row.title || ''),
      place: String(row.place || ''),
      visitDate: String(row.visitDate || ''),
      visitTime: String(row.visitTime || ''),
      leadPhone: String(row.leadPhone || ''),
      leadPhones: Array.isArray(row.leadPhones) ? row.leadPhones.map((phone) => String(phone || '')) : [],
      followUpAutoDay: String(row.followUpAutoDay || ''),
    }));
  }

  private async markSent(visit: StoredVisit): Promise<void> {
    await this.db.collection(RECORDS).updateOne(
      { _id: visit.rawId },
      { $set: { followUpAutoDay: visit.visitDate } },
    );
  }
}
