import { randomBytes } from 'node:crypto';
import { sendReportEmail } from '../reports/report-email';

export interface PendingEmailDeps {
  findPending: () => Promise<Array<Record<string, unknown>>>;
  markSent: (postId: string, batchId: string) => Promise<void>;
  fetchImpl?: typeof fetch;
}

function enabled(): boolean {
  return ['1', 'true', 'yes', 'on'].includes((process.env.EMAIL_ENABLED || '').trim().toLowerCase());
}

function subjectFor(article: Record<string, unknown>): string {
  let title = String(article.title || 'News Update').trim();
  if (title.length > 55) title = `${title.slice(0, 52)}...`;
  const source = String(article.source || 'lokal');
  const category = String(article.category || 'News');
  const stamp = new Date().toLocaleString('en-IN', { timeZone: process.env.REPORT_TIMEZONE || 'Asia/Kolkata', hour12: true });
  return `MediaSphere Alert | ${source} | ${category} | ${stamp} IST | ${title}`;
}

function htmlFor(article: Record<string, unknown>): string {
  const title = String(article.title || 'News Update');
  const summary = String(article.summary || article.problem || '');
  const source = String(article.source || '');
  const link = String(article.source_url || article.url || '');
  const linkHtml = link ? `<p><a href="${link}">Open article</a></p>` : '';
  return `<h2>${title}</h2><p>${summary}</p><p>Source: ${source}</p>${linkHtml}`;
}

/**
 * Flask incremental email: one message per article still marked email_sent=false.
 * Does not query Mongo unless email is enabled and findPending is invoked.
 */
export interface PendingEmailResult {
  sent: number;
  failed: number;
  skipped: boolean;
  pending: number;
  lastError: string | null;
}

export async function notifyPendingEmail(deps: PendingEmailDeps): Promise<PendingEmailResult> {
  if (!enabled()) return { sent: 0, failed: 0, skipped: true, pending: 0, lastError: null };
  const docs = await deps.findPending();
  if (!docs.length) return { sent: 0, failed: 0, skipped: true, pending: 0, lastError: null };
  const batchId = randomBytes(8).toString('hex');
  let sent = 0;
  let failed = 0;
  let lastError: string | null = null;
  for (const doc of docs) {
    const postId = doc.post_id ? String(doc.post_id) : '';
    let result;
    try {
      result = await sendReportEmail(subjectFor(doc), htmlFor(doc), null, undefined, deps.fetchImpl || fetch);
    } catch (err) {
      return { sent, failed: failed + 1, skipped: false, pending: docs.length, lastError: err instanceof Error ? err.message : String(err) };
    }
    if (result.success && postId) {
      sent += 1;
      await deps.markSent(postId, batchId);
    } else if (result.success) {
      failed += 1;
      lastError = 'sent but article has no post_id to mark';
    } else if (!result.skipped) {
      failed += 1;
      lastError = result.error;
    }
  }
  return { sent, failed, skipped: sent === 0 && failed === 0, pending: docs.length, lastError };
}
