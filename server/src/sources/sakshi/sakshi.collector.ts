import { load } from 'cheerio';
import { validateConstituency } from '../../pipeline/native/constituency';
import {
  SAKSHI_COLLECTOR_NAME,
  sakshiBaseUrl,
  sakshiLinkSelector,
  sakshiMaxArticles,
  sakshiRequestDelayMs,
  sakshiTagUrl,
  sakshiTagUrls,
} from './sakshi.constants';
import { extractSakshiArticle } from './sakshi.extractor';
import { PermanentHttpError, fetchSakshiHtml } from './sakshi.http';
import type { SakshiCollectorEnvelope, SakshiFilterStats } from './sakshi.models';
import { normalizeSakshiArticle } from './sakshi.normalizer';
import {
  isArticleUrl,
  isSectionHubUrl,
  linkPriority,
  loadUrlPriorityKeywords,
  resolveSakshiUrl,
} from './sakshi.parser';
export interface SakshiCollection {
  envelope: SakshiCollectorEnvelope;
  linksFound: number;
  skippedExisting: number;
  error?: string;
}

export interface CollectSakshiOptions {
  fetchImpl?: typeof fetch;
  existingUrls?: Set<string>;
  requestDelayMs?: number;
  maxArticles?: number;
  now?: Date;
  retryDelayMs?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Round-robin across tag pages so one busy segment cannot use the whole per-run limit. */
function interleaveUnique(lists: string[][]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  const longest = Math.max(0, ...lists.map((list) => list.length));
  for (let row = 0; row < longest; row += 1) {
    for (const list of lists) {
      const url = list[row];
      if (url && !seen.has(url)) {
        seen.add(url);
        out.push(url);
      }
    }
  }
  return out;
}

/**
 * Links on the Narasaraopet tag page that name a constituency place.
 * Sidebar and national links (priority under 100) are not downloaded.
 */
export function rankSakshiLinks(html: string, baseUrl = sakshiBaseUrl()): string[] {
  const page = load(html);
  const keywords = loadUrlPriorityKeywords();
  const ranked: Array<[number, number, string]> = [];
  const seen = new Set<string>();
  page(sakshiLinkSelector()).each((index, element) => {
    const href = (page(element).attr('href') || '').trim();
    if (!href) return;
    let absolute: string;
    try {
      absolute = resolveSakshiUrl(href, baseUrl);
    } catch {
      return;
    }
    if (seen.has(absolute) || !isArticleUrl(absolute) || isSectionHubUrl(absolute)) return;
    seen.add(absolute);
    const anchorText = page(element).text().replace(/\s+/g, ' ').trim();
    const priority = linkPriority(absolute, anchorText, keywords);
    if (priority < 100) return;
    ranked.push([priority, -index, absolute]);
  });
  ranked.sort((a, b) => b[0] - a[0] || b[1] - a[1]);
  return ranked.map((row) => row[2]);
}

/**
 * One Sakshi cycle for the Narasaraopet tag.
 * Does not read or write MongoDB. Pass existingUrls when a caller already knows them.
 */
export async function collectSakshiNews(options: CollectSakshiOptions = {}): Promise<SakshiCollection> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const now = options.now ?? new Date();
  const existing = options.existingUrls ?? new Set<string>();
  const maxArticles = options.maxArticles ?? sakshiMaxArticles();
  const requestDelayMs = options.requestDelayMs ?? sakshiRequestDelayMs();
  const tagUrl = sakshiTagUrl();
  const emptyStats = (): SakshiFilterStats => ({
    fetched: 0,
    accepted: 0,
    rejected: 0,
    rejected_reasons: {},
    scores: [],
  });

  const finish = (
    articles: SakshiCollectorEnvelope['articles'],
    stats: SakshiFilterStats,
    linksFound: number,
    skippedExisting: number,
    error?: string,
  ): SakshiCollection => ({
    linksFound,
    skippedExisting,
    error,
    envelope: {
      generated_at: now.toISOString(),
      collector: SAKSHI_COLLECTOR_NAME,
      source: tagUrl,
      source_name: 'sakshi',
      total_articles: articles.length,
      filter_stats: stats,
      articles,
    },
  });

  const perTag: string[][] = [];
  let firstError: string | null = null;
  for (const [index, url] of sakshiTagUrls().entries()) {
    if (index > 0 && requestDelayMs > 0) await sleep(requestDelayMs);
    try {
      const html = await fetchSakshiHtml(url, fetchImpl, { retryDelayMs: options.retryDelayMs });
      perTag.push(rankSakshiLinks(html));
    } catch (err) {
      const status = err instanceof PermanentHttpError ? err.statusCode : 0;
      firstError ??= status ? `sakshi_http_${status}` : 'sakshi_fetch_failed';
    }
  }
  if (!perTag.length) return finish([], emptyStats(), 0, 0, firstError || 'sakshi_fetch_failed');

  const links = interleaveUnique(perTag);
  const fresh = links.filter((url) => !existing.has(url));
  const pending = fresh.slice(0, maxArticles);
  const stats = emptyStats();
  const articles: SakshiCollectorEnvelope['articles'] = [];

  for (let index = 0; index < pending.length; index += 1) {
    if (index > 0 && requestDelayMs > 0) await sleep(requestDelayMs);
    const url = pending[index];
    let pageHtml: string;
    try {
      pageHtml = await fetchSakshiHtml(url, fetchImpl, { retryDelayMs: options.retryDelayMs });
    } catch {
      continue;
    }
    const raw = extractSakshiArticle(pageHtml, url);
    if (!raw) continue;
    stats.fetched += 1;
    const score = await validateConstituency(raw as unknown as Record<string, unknown>, fetchImpl);
    stats.scores.push(score.score);
    if (!score.valid) {
      stats.rejected += 1;
      stats.rejected_reasons[score.reason] = (stats.rejected_reasons[score.reason] || 0) + 1;
      continue;
    }
    stats.accepted += 1;
    raw._constituency_validation = { valid: score.valid, score: score.score, reason: score.reason, segment: score.segment };
    articles.push(normalizeSakshiArticle(raw, now));
  }

  return finish(articles, stats, links.length, links.length - fresh.length);
}
