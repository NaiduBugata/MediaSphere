import { YOUTUBE_TRANSCRIPT_LANGUAGES } from './youtube.constants';
import { extractCaptionTracks, parseCaptionText, pickTeluguTrack } from './youtube.parser';

const WATCH_HEADERS: Record<string, string> = {
  'Accept-Language': 'te',
  'User-Agent': 'MediaSphereBot/1.0',
};

export interface TranscriptResult {
  text: string | null;
  /** `ok`, `no_captions` when YouTube answered normally without a Telugu track, otherwise why YouTube refused. */
  reason: string;
}

async function fetchInnertubeTranscript(videoId: string, fetchImpl: typeof fetch): Promise<TranscriptResult> {
  const response = await fetchImpl('https://www.youtube.com/youtubei/v1/player?prettyPrint=false', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'com.google.android.youtube/20.10.38 (Linux; U; Android 14)',
    },
    body: JSON.stringify({
      context: { client: { clientName: 'ANDROID', clientVersion: '20.10.38', hl: 'te' } },
      videoId,
    }),
  });
  if (!response.ok) return { text: null, reason: `player_http_${response.status}` };
  const payload = (await response.json()) as {
    playabilityStatus?: { status?: string };
    captions?: { playerCaptionsTracklistRenderer?: { captionTracks?: Array<{ baseUrl?: string; languageCode?: string }> } };
  };
  const playability = payload.playabilityStatus?.status || 'UNKNOWN';
  if (playability !== 'OK') return { text: null, reason: `playability_${playability.toLowerCase()}` };
  const tracks = payload.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
  const track = pickTeluguTrack(
    tracks
      .filter((row) => row.baseUrl)
      .map((row) => ({ baseUrl: String(row.baseUrl), languageCode: String(row.languageCode || '') })),
  );
  if (!track) return { text: null, reason: 'no_captions' };
  const caption = await fetchImpl(track.baseUrl);
  if (!caption.ok) return { text: null, reason: `caption_http_${caption.status}` };
  const text = parseCaptionText(await caption.text());
  return text ? { text, reason: 'ok' } : { text: null, reason: 'caption_empty' };
}

/**
 * Telugu captions only, matching youtube_transcript_api languages=['te'].
 * The player endpoint returns a usable caption URL. Watch-page tracks and
 * timedtext are fallbacks when that URL is empty.
 */
export async function fetchTeluguTranscriptResult(
  videoId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<TranscriptResult> {
  const language = YOUTUBE_TRANSCRIPT_LANGUAGES[0];
  let primary: TranscriptResult = { text: null, reason: 'player_failed' };
  try {
    primary = await fetchInnertubeTranscript(videoId, fetchImpl);
    if (primary.text) return primary;
  } catch {
    // Watch-page captions are the fallback.
  }
  try {
    const watch = await fetchImpl(`https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}`, {
      headers: WATCH_HEADERS,
    });
    if (watch.ok) {
      const track = pickTeluguTrack(extractCaptionTracks(await watch.text()));
      if (track) {
        const caption = await fetchImpl(track.baseUrl);
        if (caption.ok) {
          const text = parseCaptionText(await caption.text());
          if (text) return { text, reason: 'ok' };
        }
      }
    }
  } catch {
    // Timedtext below is the fallback.
  }
  try {
    const timed = await fetchImpl(
      `https://www.youtube.com/api/timedtext?v=${encodeURIComponent(videoId)}&lang=${language}`,
    );
    if (timed.ok) {
      const text = parseCaptionText(await timed.text());
      if (text) return { text, reason: 'ok' };
    }
  } catch {
    // The primary reason is reported.
  }
  return primary;
}

export async function fetchTeluguTranscript(
  videoId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<string | null> {
  return (await fetchTeluguTranscriptResult(videoId, fetchImpl)).text;
}
