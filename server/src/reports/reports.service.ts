import { Injectable, Logger } from '@nestjs/common';
import { resolve } from 'node:path';
import { Document } from 'mongodb';
import { ArticleRepository } from '../database/repositories/article.repository';
import { DailyReportRepository } from '../database/repositories/daily-report.repository';
import { buildEmailHtml } from './report-html';
import { writeTextPdf } from './report-pdf';
import { generateExecutiveSummary } from './report-summary';
import {
  articlesForDay,
  computeStats,
  formatLongDate,
  previousReportDay,
  type ReportArticle,
  type ReportStats,
} from './report-stats';
import { notifyDailyWhatsApp } from '../whatsapp/whatsapp.notify';

export interface ReportRunResult {
  status: string;
  report_date: string;
  reason?: string;
  error?: string | null;
  recipients?: string[];
  attempts?: number;
  articles_included?: number;
  problems_count?: number;
  positive_count?: number;
  negative_count?: number;
  pdf_path?: string;
  subject?: string;
  notifications?: { results: Array<Record<string, unknown>> };
}

export interface GenerateOptions {
  force?: boolean;
  recipients?: string[];
  articles?: ReportArticle[];
  sourceDocs?: Array<Record<string, unknown>>;
  fetchImpl?: typeof fetch;
  now?: Date;
}

@Injectable()
export class ReportsService {
  private readonly logger = new Logger(ReportsService.name);

  constructor(
    private readonly reports: DailyReportRepository,
    private readonly articles: ArticleRepository,
  ) {}

  async history(limit = 60): Promise<Document[]> {
    return this.reports.history(limit);
  }

  async getById(reportId: string): Promise<Document | null> {
    return this.reports.getById(reportId);
  }

  /** Build and record a report, then send the summary on WhatsApp. Reports are never emailed. */
  async generateAndSend(target: string | null, options: GenerateOptions = {}): Promise<ReportRunResult> {
    const day = target || previousReportDay(options.now || new Date());
    if (!options.force && (await this.reports.alreadySent(day))) {
      this.logger.log(`Report for ${day} already sent; skipping.`);
      return { status: 'skipped', reason: 'already_sent', report_date: day };
    }
    try {
      const built = await this.build(day, options);
      const recipients: string[] = [];
      await this.reports.recordGeneration(day, built.stats, recipients, built.pdfPath);
      const whatsapp = await notifyDailyWhatsApp(
        { total: built.stats.total, positive: built.stats.positive, negative: built.stats.negative, problems: built.stats.problems },
        day,
        options.fetchImpl || fetch,
      );
      const notifications = { results: [{ channel: 'whatsapp', ...whatsapp }] };
      if (whatsapp.success && !whatsapp.skipped) {
        await this.reports.recordSent(day, whatsapp.attempts);
        return this.outcome('sent', day, built, recipients, whatsapp.attempts, null, notifications);
      }
      const error = whatsapp.skipped ? `whatsapp_skipped: ${whatsapp.skip_reason || 'unknown'}` : whatsapp.error || 'unknown';
      await this.reports.recordFailed(day, whatsapp.attempts, error);
      return this.outcome('failed', day, built, recipients, whatsapp.attempts, error, notifications);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.logger.error(`Report build failed for ${day}: ${message}`);
      await this.reports.recordFailed(day, 0, `build_failed: ${message}`);
      return { status: 'error', reason: 'build_failed', error: message, report_date: day };
    }
  }

  private async build(day: string, options: GenerateOptions): Promise<{
    stats: ReportStats;
    html: string;
    pdfPath: string;
    subject: string;
  }> {
    const now = options.now || new Date();
    let articles = options.articles;
    if (!articles) {
      const docs = options.sourceDocs || ((await this.articles.findAll()) as Array<Record<string, unknown>>);
      articles = articlesForDay(docs, day);
    }
    const stats = computeStats(articles);
    const summary = await generateExecutiveSummary(day, articles, stats, options.fetchImpl || fetch);
    const html = buildEmailHtml(day, now, articles, stats, summary);
    const pdfPath = resolve(
      process.cwd(),
      process.env.REPORT_OUTPUT_DIR || 'reports_output',
      `Daily_Report_${day.replace(/-/g, '_')}.pdf`,
    );
    writeTextPdf(pdfPath, [
      'MediaSphere Daily Constituency Report',
      formatLongDate(day),
      '',
      'Executive Summary',
      summary,
      '',
      `Articles: ${stats.total}`,
      `Problems: ${stats.problems}`,
      `Positive: ${stats.positive}`,
      `Negative: ${stats.negative}`,
    ]);
    return { stats, html, pdfPath, subject: `MediaSphere Daily Constituency Report - ${formatLongDate(day)}` };
  }

  private outcome(
    status: string,
    day: string,
    built: { stats: ReportStats; pdfPath: string; subject: string },
    recipients: string[],
    attempts: number,
    error: string | null,
    notifications: { results: Array<Record<string, unknown>> },
  ): ReportRunResult {
    return {
      status,
      report_date: day,
      recipients,
      attempts,
      error,
      articles_included: built.stats.total,
      problems_count: built.stats.problems,
      positive_count: built.stats.positive,
      negative_count: built.stats.negative,
      pdf_path: built.pdfPath,
      subject: built.subject,
      notifications,
    };
  }
}
