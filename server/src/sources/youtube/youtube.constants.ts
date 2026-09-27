/** YouTube collector settings. Defaults match server/sources/youtube/config.py. */

function intEnv(name: string, fallback: number, min = 0): number {
  const raw = process.env[name];
  if (raw == null || raw.trim() === '') return fallback;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.trunc(parsed));
}

export function youtubeEnabled(): boolean {
  const raw = (process.env.YOUTUBE_ENABLED || 'true').toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes' || raw === 'on';
}

export function youtubeApiKey(): string {
  return (process.env.YOUTUBE_API_KEY || '').trim();
}

export function youtubeSearchPeriodDays(): number {
  return intEnv('YOUTUBE_SEARCH_PERIOD_DAYS', 2, 1);
}

export function youtubeMaxResultsPerKeyword(): number {
  return intEnv('YOUTUBE_MAX_RESULTS_PER_KEYWORD', 50, 1);
}

export function youtubeMaxNewPerRun(): number {
  return intEnv('YOUTUBE_MAX_NEW_PER_RUN', 30, 1);
}

export function youtubeMinContentChars(): number {
  return intEnv('YOUTUBE_MIN_CONTENT_CHARS', 100, 1);
}

export function youtubeMaxContentChars(): number {
  return intEnv('YOUTUBE_MAX_CONTENT_CHARS', 6000, 1);
}

export const YOUTUBE_TRANSCRIPT_LANGUAGES = ['te'];

/** Constituency searches from server/sources/youtube/config.py. */
export const YOUTUBE_SEARCH_KEYWORDS = [
  'నరసరావుపేట',
  'పల్నాడు',
  'Narasaraopet',
  'Palnadu',
  'చిలకలూరిపేట',
  'సత్తెనపల్లి',
  'వినుకొండ',
  'Chilakaluripet',
  'Sattenapalli',
  'Vinukonda',
  'పిడుగురాళ్ళ',
  'Piduguralla',
  'మాచర్ల',
  'Macherla',
  'రొంపిచర్ల',
  'Rompicherla',
];

export const YOUTUBE_COLLECTOR_NAME = 'YouTube News Collector';
