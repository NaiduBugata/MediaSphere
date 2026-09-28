/** Normalized article saved by the Lokal collector (sources/lokal/models.py). */
export interface LokalArticle {
  id: string | number;
  title: string;
  content: string;
  created_on: string;
  url: string;
  raw: Record<string, unknown>;
  _constituency_validation?: {
    valid: boolean;
    score: number;
    reason: string;
    segment: string | null;
  };
}

export interface LokalCollectorEnvelope {
  generated_at: string;
  collector: string;
  source: string;
  tag_id: number;
  lookback_hours: number;
  total_articles: number;
  articles: LokalArticle[];
}
