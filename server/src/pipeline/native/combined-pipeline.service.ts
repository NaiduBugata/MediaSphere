import { createHash } from 'node:crypto';
import { Injectable, Logger } from '@nestjs/common';
import { DatabaseService } from '../../database/database.service';
import { analyzeNewsArticle } from '../../ai/groq-analyzer';
import { titlesMatch } from './fuzzy-title';
import type { BridgeResult, CycleStats } from '../python-bridge.service';
import { emptyStats } from '../python-bridge.service';
import type {
  CollectedArticle,
  SourceCollectionResult,
  SourceName,
} from '../../sources/source-collector';
import { collectLokalNews } from '../../sources/lokal/lokal.collector';
import { collectSakshiNews } from '../../sources/sakshi/sakshi.collector';
import { collectYoutubeNews } from '../../sources/youtube/youtube.collector';
import { mergeSourceResults } from '../combined-cycle';
import { notifyFailureWhatsApp, notifyPendingWhatsApp, notifyPipelineWhatsApp } from '../../whatsapp/whatsapp.notify';
import { describeFailure, FailureAlertGate, pipelineStatusWhatsAppEnabled } from './pipeline-alerts';
import { ASSEMBLY_SEGMENTS, scoreConstituency, type AssemblySegment } from './constituency';
import { whatsappReady } from '../../whatsapp/whatsapp.send';
import { sendPipelineFailureEmail } from '../../notifications/failure-email';

function httpUrl(value: unknown): string {
  if (typeof value !== 'string') return '';
  const url = value.trim();
  return url.startsWith('http://') || url.startsWith('https://') ? url : '';
}

/** First usable picture on a Lokal post (`images` is an object or a list). */
function lokalThumbnail(raw: Record<string, unknown> | undefined): string {
  if (!raw) return '';
  const images = raw.images;
  const list = Array.isArray(images) ? images : images ? [images] : [];
  for (const item of list) {
    if (!item || typeof item !== 'object') {
      const direct = httpUrl(item);
      if (direct) return direct;
      continue;
    }
    const row = item as Record<string, unknown>;
    const found = httpUrl(row.image) || httpUrl(row.thumb_url) || httpUrl(row.url);
    if (found) return found;
  }
  return httpUrl(raw.image) || httpUrl(raw.thumb_url);
}

export interface NativeCycleHooks {
  fetchImpl?: typeof fetch;
  now?: () => Date;
}

/**
 * Nest combined cycle: Lokal → YouTube → Sakshi → Groq stages → upsert → notify.
 * News goes to WhatsApp only. Email is sent only when a cycle fails.
 * Sequential, matching Flask pipeline/runner.py. Notification errors never roll back writes.
 * PIPELINE_EXECUTOR=python keeps the Phase 3 bridge for tests.
 */
@Injectable()
export class CombinedPipelineService {
  private readonly logger = new Logger(CombinedPipelineService.name);
  private readonly failureAlerts = new FailureAlertGate();

  constructor(private readonly db: DatabaseService) {}

  async runCombinedOnce(hooks: NativeCycleHooks = {}): Promise<BridgeResult> {
    const started = Date.now();
    const fetchImpl = hooks.fetchImpl ?? fetch;
    const maxAnalyze = Number(process.env.PIPELINE_MAX_ANALYZE || '8');
    const errors: string[] = [];
    const results: SourceCollectionResult[] = [];

    results.push(await this.safeCollect('lokal', () => this.collectLokal(fetchImpl)));
    results.push(
      await this.safeCollect('youtube', () => this.collectYoutube(fetchImpl)),
    );
    results.push(
      await this.safeCollect('sakshi', () => this.collectSakshi(fetchImpl)),
    );

    const mapped: CollectedArticle[] = [];
    for (const article of results.flatMap((r) => r.articles)) {
      const segment = resolveSegment(article);
      if (!segment) {
        this.logger.warn(`[SEGMENT_GATE] dropped source=${article.source} post_id=${article.post_id}: not one of the 7 assembly segments`);
        continue;
      }
      mapped.push({ ...article, assembly_segment: segment });
    }
    const articles = mapped.slice(0, maxAnalyze);
    let inserted = 0;
    let duplicates = 0;
    let aiFailed = 0;
    let aiOk = 0;

    for (const article of articles) {
      try {
        const analyzed = await this.analyze(article, fetchImpl);
        const outcome = await this.upsert(article, analyzed);
        if (outcome === 'inserted') inserted += 1;
        else duplicates += 1;
        aiOk += 1;
      } catch (err) {
        aiFailed += 1;
        const message = err instanceof Error ? err.message : String(err);
        errors.push(`${article.source}:${article.post_id}:${message.slice(0, 180)}`);
        this.logger.error(
          `[AI_FAIL] source=${article.source} post_id=${article.post_id} ${message}`,
        );
      }
    }

    const merged = mergeSourceResults(results);
    const exitCode = merged.exitCode === 0 && aiFailed === 0 ? 0 : merged.exitCode || (aiFailed ? 1 : 0);
    const stats: CycleStats = {
      ...emptyStats(),
      articles_fetched: merged.articles_fetched,
      duplicates: merged.duplicates + duplicates,
      inserted,
      lokal_processed: merged.lokal_processed,
      youtube_processed: merged.youtube_processed,
      sakshi_processed: merged.sakshi_processed,
      errors: [...merged.errors, ...errors],
    };
    if (aiFailed) stats.errors.push(`ai_failed=${aiFailed}`);

    await this.notifyPipeline(stats, exitCode, fetchImpl, Date.now() - started);

    this.logger.log(
      `[NATIVE_CYCLE] exit=${exitCode} inserted=${inserted} duplicates=${stats.duplicates} ai_ok=${aiOk} ai_failed=${aiFailed} ms=${Date.now() - started}`,
    );

    return {
      exitCode,
      stats,
      timedOut: false,
      parsed: true,
      outputTail: `ai_ok=${aiOk} ai_failed=${aiFailed}`,
      command: 'nestjs:combined-pipeline',
    };
  }

  private async safeCollect(
    source: SourceName,
    fn: () => Promise<SourceCollectionResult>,
  ): Promise<SourceCollectionResult> {
    const startedAt = new Date().toISOString();
    try {
      return await fn();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return this.emptyResult(source, startedAt, [`${source}_failed:${message.slice(0, 180)}`]);
    }
  }

  private async collectLokal(fetchImpl: typeof fetch): Promise<SourceCollectionResult> {
    const started = Date.now();
    const startedAt = new Date().toISOString();
    const collected = await collectLokalNews(fetchImpl);
    const articles: CollectedArticle[] = collected.envelope.articles.map((article) => ({
      post_id: String(article.id),
      source: 'lokal',
      title: article.title,
      content: article.content,
      created_on: article.created_on,
      source_url: article.url,
      thumbnail: lokalThumbnail(article.raw),
      assembly_segment: article._constituency_validation?.segment ?? null,
    }));
    return {
      source: 'lokal',
      status: 'success',
      startedAt,
      completedAt: new Date().toISOString(),
      durationMs: Date.now() - started,
      itemsFound: articles.length,
      itemsNew: articles.length,
      itemsDuplicate: collected.duplicatesRemoved,
      itemsFailed: collected.constituencyRejected,
      errors: [],
      articles,
      exitCode: 0,
    };
  }

  private async collectYoutube(fetchImpl: typeof fetch): Promise<SourceCollectionResult> {
    const startedAt = new Date().toISOString();
    const started = Date.now();
    if (process.env.YOUTUBE_ENABLED === 'false') {
      return { ...this.emptyResult('youtube', startedAt, []), status: 'skipped', exitCode: 0 };
    }
    const collected = await collectYoutubeNews({ fetchImpl });
    if (collected.error) {
      return this.emptyResult('youtube', startedAt, [collected.error]);
    }
    const blockedReasons = Object.entries(collected.blocked).map(([reason, count]) => `${reason}=${count}`).join(',') || 'none';
    this.logger.log(
      `[YOUTUBE] videos=${collected.videosFound} articles=${collected.envelope.articles.length} no_captions=${collected.noCaptions} blocked=${blockedReasons} non_news=${collected.nonNews} other_constituency=${collected.constituencyRejected}`,
    );
    const articles: CollectedArticle[] = collected.envelope.articles.map((article) => ({
      post_id: `yt_${article.video_id}`,
      source: 'youtube',
      title: article.title,
      content: article.content,
      created_on: article.created_on,
      source_url: article.url,
      thumbnail: article.video_id
        ? `https://i.ytimg.com/vi/${article.video_id}/hqdefault.jpg`
        : '',
      assembly_segment: article.assembly_segment ?? null,
    }));
    if (!articles.length && collected.errors.length) {
      return this.emptyResult('youtube', startedAt, collected.errors.slice(0, 8));
    }
    return {
      source: 'youtube',
      status: 'success',
      startedAt,
      completedAt: new Date().toISOString(),
      durationMs: Date.now() - started,
      itemsFound: articles.length,
      itemsNew: articles.length,
      itemsDuplicate: 0,
      itemsFailed: 0,
      errors: [],
      articles,
      exitCode: 0,
    };
  }

  private async collectSakshi(fetchImpl: typeof fetch): Promise<SourceCollectionResult> {
    const startedAt = new Date().toISOString();
    const started = Date.now();
    if (process.env.SAKSHI_ENABLED === 'false') {
      return { ...this.emptyResult('sakshi', startedAt, []), status: 'skipped', exitCode: 0 };
    }
    const collected = await collectSakshiNews({ fetchImpl });
    if (collected.error) {
      return this.emptyResult('sakshi', startedAt, [collected.error]);
    }
    const articles: CollectedArticle[] = collected.envelope.articles.map((article) => ({
      post_id: article.id.startsWith('sakshi_') ? article.id : `sakshi_${article.id}`,
      source: 'sakshi',
      title: article.title,
      content: article.content,
      created_on: article.created_on,
      source_url: article.source_url,
      thumbnail: article.thumbnail || '',
      assembly_segment: article.assembly_segment,
    }));
    this.logger.log(
      `[SAKSHI] links=${collected.linksFound} already_saved=${collected.skippedExisting} new=${articles.length} rejected=${collected.envelope.filter_stats.rejected}`,
    );
    if (!collected.linksFound) return this.emptyResult('sakshi', startedAt, ['sakshi_no_links']);
    return {
      source: 'sakshi',
      status: 'success',
      startedAt,
      completedAt: new Date().toISOString(),
      durationMs: Date.now() - started,
      itemsFound: articles.length,
      itemsNew: articles.length,
      itemsDuplicate: collected.skippedExisting,
      itemsFailed: collected.envelope.filter_stats.rejected,
      errors: [],
      articles,
      exitCode: 0,
    };
  }

  /** Python Groq analyzer: three stages, normalize, validate, quality, problem id. */
  async analyze(
    article: CollectedArticle,
    fetchImpl: typeof fetch = fetch,
  ): Promise<Record<string, unknown>> {
    return analyzeNewsArticle(
      {
        articleId: article.post_id,
        title: article.title,
        content: article.content || '',
      },
      fetchImpl,
    );
  }

  private async upsert(
    article: CollectedArticle,
    analyzed: Record<string, unknown>,
  ): Promise<'inserted' | 'duplicate'> {
    await this.db.ensureConnected();
    const coll = this.db.collection(this.db.articlesCollectionName);
    const now = new Date().toISOString();
    const fingerprint = createHash('sha256')
      .update(
        `${(article.title || '').trim()}|${(article.content || '').trim()}|${article.created_on || ''}|${article.source}`,
        'utf8',
      )
      .digest('hex');
    const doc = {
      post_id: article.post_id,
      source: article.source,
      title: article.title,
      summary: analyzed.summary,
      sentiment: analyzed.sentiment,
      category: analyzed.category,
      subcategory: analyzed.subcategory,
      problem: analyzed.problem,
      problem_id: analyzed.problem_id,
      severity: analyzed.severity,
      authority: analyzed.authority,
      location: analyzed.location,
      entities: analyzed.entities,
      keywords: analyzed.keywords,
      source_url: article.source_url || null,
      created_on: article.created_on || null,
      constituency: 'Narasaraopet',
      assembly_segment: article.assembly_segment,
      ...(article.thumbnail ? { thumbnail: article.thumbnail } : {}),
      content_fingerprint: fingerprint,
      last_updated_at: now,
    };
    let prior: Array<{ title?: string; post_id?: string }> = [];
    try {
      prior = (await coll
        .find({ source: article.source })
        .limit(15)
        .toArray()) as Array<{ title?: string; post_id?: string }>;
    } catch {
      prior = [];
    }
    for (const row of prior) {
      if (row.post_id !== article.post_id && titlesMatch(article.title, String(row.title || ''))) {
        return 'duplicate';
      }
    }
    try {
      const result = await coll.updateOne(
        { post_id: article.post_id },
        {
          $set: doc,
          $setOnInsert: {
            first_seen_at: now,
            whatsapp_sent: false,
          },
        },
        { upsert: true },
      );
      return result.upsertedCount > 0 ? 'inserted' : 'duplicate';
    } catch (err) {
      const code = (err as { code?: number }).code;
      if (code === 11000) return 'duplicate';
      throw err;
    }
  }

  private async notifyPipeline(
    stats: CycleStats,
    exitCode: number,
    fetchImpl: typeof fetch,
    durationMs: number,
  ): Promise<void> {
    this.logger.log(
      `[NOTIFY_PIPELINE] exit=${exitCode} inserted=${stats.inserted} errors=${stats.errors.length}`,
    );
    if (exitCode === 0) this.failureAlerts.clear();
    else await this.alertFailure(stats.errors, fetchImpl);
    try {
      if (!whatsappReady()) return;
      const payload = {
        ...stats,
        duration_seconds: Math.round(durationMs / 1000),
        status: exitCode === 0 ? 'Finished Successfully' : 'Completed with errors',
      };
      await notifyPendingWhatsApp({
        fetchImpl,
        findPending: async () => {
          await this.db.ensureConnected();
          const rows = await this.db.collection(this.db.articlesCollectionName).find({ whatsapp_sent: false }).toArray();
          return rows as Array<Record<string, unknown>>;
        },
        markSent: async (postId, messageId, critical) => {
          const now = new Date().toISOString();
          const update: Record<string, unknown> = {
            whatsapp_sent: true,
            whatsapp_sent_at: now,
            whatsapp_message_id: messageId,
          };
          if (critical) {
            update.whatsapp_critical_sent = true;
            update.whatsapp_critical_sent_at = now;
          }
          await this.db.collection(this.db.articlesCollectionName).updateOne({ post_id: postId }, { $set: update });
        },
      });
      if (pipelineStatusWhatsAppEnabled()) await notifyPipelineWhatsApp(payload, fetchImpl);
    } catch (err) {
      this.logger.error(
        'notification failed (ignored): ' + (err instanceof Error ? err.message : String(err)),
      );
    }
  }

  /**
   * Failure alert on WhatsApp and email. A new problem alerts at once; the same problem
   * repeats only after PIPELINE_ALERT_REPEAT_HOURS. Never throws.
   */
  async alertFailure(errors: readonly string[], fetchImpl: typeof fetch = fetch): Promise<void> {
    const reason = describeFailure(errors).slice(0, 500);
    if (!this.failureAlerts.shouldAlert(errors, Date.now())) {
      this.logger.warn(`[NOTIFY_FAILURE] same problem as the last alert; WhatsApp and email skipped: ${reason}`);
      return;
    }
    if (whatsappReady()) {
      try {
        await notifyFailureWhatsApp('combined_pipeline', reason, 'N/A', fetchImpl);
      } catch (err) {
        this.logger.error(`[NOTIFY_FAILURE] WhatsApp failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
    try {
      const email = await sendPipelineFailureEmail({ reason, errors, fetchImpl });
      if (email.success) this.logger.log('[NOTIFY_FAILURE_EMAIL] sent');
      else if (email.skipped) this.logger.log(`[NOTIFY_FAILURE_EMAIL] skipped: ${email.skip_reason}`);
      else this.logger.error(`[NOTIFY_FAILURE_EMAIL] failed: ${String(email.error).slice(0, 300)}`);
    } catch (err) {
      this.logger.error(`[NOTIFY_FAILURE_EMAIL] failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  private emptyResult(
    source: SourceName,
    startedAt: string,
    errors: string[],
  ): SourceCollectionResult {
    return {
      source,
      status: errors.length ? 'failed' : 'success',
      startedAt,
      completedAt: new Date().toISOString(),
      durationMs: 0,
      itemsFound: 0,
      itemsNew: 0,
      itemsDuplicate: 0,
      itemsFailed: errors.length ? 1 : 0,
      errors,
      articles: [],
      exitCode: errors.length ? 1 : 0,
    };
  }
}

/** Port of DecisionEngine.decide. */
export function decide(
  results: Array<Record<string, unknown>>,
  retriesRemaining: number,
): 'accept' | 'retry' | 'reject' {
  if (results.some((r) => r.severity === 'CRITICAL')) return 'reject';
  const unrepaired = results.some((r) => r.severity === 'ERROR' && !r.repaired);
  if (unrepaired) return retriesRemaining > 0 ? 'retry' : 'reject';
  return 'accept';
}

/** The segment a collector assigned, or a fresh full check. Anything else is outside the constituency. */
export function resolveSegment(article: CollectedArticle): AssemblySegment | null {
  const assigned = article.assembly_segment;
  if (assigned && (ASSEMBLY_SEGMENTS as readonly string[]).includes(assigned)) return assigned as AssemblySegment;
  const checked = scoreConstituency(`${article.title || ''}\n${article.content || ''}`);
  return checked.valid ? checked.segment : null;
}

function dedupeById(articles: CollectedArticle[]): CollectedArticle[] {
  const map = new Map<string, CollectedArticle>();
  for (const article of articles) map.set(article.post_id, article);
  return [...map.values()];
}
