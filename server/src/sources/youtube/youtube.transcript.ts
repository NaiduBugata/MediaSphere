import { YOUTUBE_TRANSCRIPT_LANGUAGES } from './youtube.constants';
import { extractCaptionTracks, parseCaptionText, pickTeluguTrack } from './youtube.parser';

const WATCH_HEADERS: Record<string, string> = {
  'Accept-Language': 'te',
  'User-Agent': 'MediaSphereBot/1.0',
};

/**
 * Telugu captions only, matching youtube_transcript_api languages=['te'].
 * The player endpoint returns a usable caption URL. Watch-page tracks and
 * timedtext are fallbacks when that URL is empty.
 */
async function fetchInnertubeTranscript(videoId: string, fetchImpl: typeof fetch): Promise<string | null> {
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
  if (!response.ok) return null;
  const payload = (await response.json()) as {
    captions?: { playerCaptionsTracklistRenderer?: { captionTracks?: Array<{ baseUrl?: string; languageCode?: string }> } };
  };
  const tracks = payload.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
  const track = pickTeluguTrack(
    tracks
      .filter((row) => row.baseUrl)
      .map((row) => ({ baseUrl: String(row.baseUrl), languageCode: String(row.languageCode || '') })),
  );
  if (!track) return null;
  const caption = await fetchImpl(track.baseUrl);
  if (!caption.ok) return null;
  const text = parseCaptionText(await caption.text());
  return text || null;
}

export async function fetchTeluguTranscript(
  videoId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<string | null> {
  const language = YOUTUBE_TRANSCRIPT_LANGUAGES[0];
  try {
    const innertube = await fetchInnertubeTranscript(videoId, fetchImpl);
    if (innertube) return innertube;
  } catch {
    // Watch-page captions are the fallback.
  }
  try {
    const watch = await fetchImpl(`https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}`, {
      headers: WATCH_HEADERS,
    });
    if (watch.ok) {
      const tracks = extractCaptionTracks(await watch.text());
      const track = pickTeluguTrack(tracks);
      if (track) {
        const caption = await fetchImpl(track.baseUrl);
        if (caption.ok) {
          const text = parseCaptionText(await caption.text());
          if (text) return text;
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
    if (!timed.ok) return null;
    const text = parseCaptionText(await timed.text());
    return text || null;
  } catch {
    return null;
  }
}
