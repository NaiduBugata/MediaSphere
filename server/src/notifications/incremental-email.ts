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
export async function notifyPendingEmail(deps: PendingEmailDeps): Promise<{ sent: number; failed: number; skipped: boolean }> {
  if (!enabled()) return { sent: 0, failed: 0, skipped: true };
  const docs = await deps.findPending();
  if (!docs.length) return { sent: 0, failed: 0, skipped: true };
  const batchId = randomBytes(8).toString('hex');
  let sent = 0;
  let failed = 0;
  for (const doc of docs) {
    const postId = doc.post_id ? String(doc.post_id) : '';
    const result = await sendReportEmail(subjectFor(doc), htmlFor(doc), null, undefined, deps.fetchImpl || fetch);
    if (result.success && postId) {
      sent += 1;
      await deps.markSent(postId, batchId);
    } else if (!result.skipped) {
      failed += 1;
    }
  }
  return { sent, failed, skipped: sent === 0 && failed === 0 };
}
