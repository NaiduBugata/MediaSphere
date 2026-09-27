import { LOKAL_LOOKBACK_HOURS } from './lokal.constants';
import { fetchLokalPage } from './lokal.api';
import type { LokalArticle } from './lokal.models';
import { normalizeArticle } from './lokal.normalizer';
import { parsePostDate } from './lokal.parser';

export interface LokalFetchStats {
  articles: LokalArticle[];
  skipped: number;
}

/**
 * Paginate the Telugu Lokal API until the lookback cutoff or the last page.
 * Port of sources/lokal/extractor.py::fetch_last_24hr_news.
 */
export async function fetchLokalWindow(
  fetchImpl: typeof fetch = fetch,
  now: Date = new Date(),
): Promise<LokalFetchStats> {
  const cutoff = now.getTime() - LOKAL_LOOKBACK_HOURS * 3600 * 1000;
  const articles: LokalArticle[] = [];
  let skipped = 0;
  let page = 1;

  while (true) {
    const payload = await fetchLokalPage(page, fetchImpl);
    if (!payload) break;
    const results = payload.results;
    if (!Array.isArray(results)) break;
    if (results.length === 0) break;

    let stop = false;
    for (const post of results) {
      if (!post || typeof post !== 'object') {
        skipped += 1;
        continue;
      }
      const row = post as Record<string, unknown>;
      const postTime = parsePostDate(row.created_on);
      if (!postTime) {
        skipped += 1;
        continue;
      }
      if (postTime.getTime() < cutoff) {
        stop = true;
        break;
      }
      const normalized = normalizeArticle(row);
      if (!normalized) {
        skipped += 1;
        continue;
      }
      articles.push(normalized);
    }

    if (stop) break;
    if (!payload.next) break;
    page += 1;
  }

  return { articles, skipped };
}
