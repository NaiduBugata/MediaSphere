import { validateConstituency } from '../../pipeline/native/constituency';
import {
  LOKAL_COLLECTOR_NAME,
  LOKAL_LOOKBACK_HOURS,
  LOKAL_SOURCE_URL,
  LOKAL_TAG_ID,
} from './lokal.constants';
import { fetchLokalWindow } from './lokal.extractor';
import type { LokalArticle, LokalCollectorEnvelope } from './lokal.models';
import { removeDuplicates } from './lokal.normalizer';

export interface LokalCollection {
  envelope: LokalCollectorEnvelope;
  duplicatesRemoved: number;
  constituencyRejected: number;
  skipped: number;
}

/**
 * One Lokal cycle: fetch the 7-day window, dedupe by id, keep constituency matches.
 * Port of sources/lokal/collector.py::run without writing a JSON file.
 */
export async function collectLokalNews(
  fetchImpl: typeof fetch = fetch,
  now: Date = new Date(),
): Promise<LokalCollection> {
  const fetched = await fetchLokalWindow(fetchImpl, now);
  const [deduped, duplicatesRemoved] = removeDuplicates(fetched.articles);
  const kept: LokalArticle[] = [];
  let constituencyRejected = 0;
  for (const article of deduped) {
    const score = await validateConstituency(
      { title: article.title, content: article.content },
      fetchImpl,
    );
    if (!score.valid) {
      constituencyRejected += 1;
      continue;
    }
    kept.push({
      ...article,
      _constituency_validation: {
        valid: score.valid,
        score: score.score,
        reason: score.reason,
        segment: score.segment,
      },
    });
  }
  return {
    duplicatesRemoved,
    constituencyRejected,
    skipped: fetched.skipped,
    envelope: {
      generated_at: now.toISOString(),
      collector: LOKAL_COLLECTOR_NAME,
      source: LOKAL_SOURCE_URL,
      tag_id: LOKAL_TAG_ID,
      lookback_hours: LOKAL_LOOKBACK_HOURS,
      total_articles: kept.length,
      articles: kept,
    },
  };
}
