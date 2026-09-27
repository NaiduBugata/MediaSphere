/** Static constants from server/sources/lokal/constants.py. */
export const LOKAL_BASE_URL = 'https://telugu.getlokalapp.com/api/posts';
export const LOKAL_SOURCE_URL = 'https://telugu.getlokalapp.com/api/posts';
export const LOKAL_WEBSITE_BASE_URL = 'https://telugu.getlokalapp.com';
export const LOKAL_TAG_ID = 374;
export const LOKAL_POST_TYPES = '1,2';
export const LOKAL_PAGE_SIZE = 100;
export const LOKAL_LOOKBACK_HOURS = 24 * 7;
export const LOKAL_TIMEOUT_MS = 20_000;
export const LOKAL_MAX_RETRIES = 3;
export const LOKAL_BACKOFF_FACTOR = 2;
export const LOKAL_RETRY_STATUSES = new Set([429, 500, 502, 503, 504]);
export const LOKAL_COLLECTOR_NAME = 'Lokal News Collector';
export const LOKAL_HEADERS: Record<string, string> = {
  'User-Agent': 'Mozilla/5.0 (compatible; LokalNewsCollector/1.0)',
  Accept: 'application/json',
};
