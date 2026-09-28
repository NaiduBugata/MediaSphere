export interface YoutubeVideo {
  video_id: string;
  title: string;
  channel: string;
  published_at: string;
  url: string;
}

export interface YoutubeTranscript extends YoutubeVideo {
  transcript: string;
}

/** Normalized article from sources/youtube/normalizer.py. */
export interface YoutubeArticle {
  id: string;
  video_id: string;
  title: string;
  content: string;
  channel: string;
  url: string;
  created_on: string;
  constituency_score?: number;
  constituency_match_reason?: string;
  assembly_segment?: string | null;
}

export interface YoutubeCollectorEnvelope {
  source: 'youtube';
  fetched_at: string;
  lookback_days: number;
  articles: YoutubeArticle[];
}
