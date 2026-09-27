export interface SakshiRawArticle {
  url: string;
  title: string;
  content: string;
  summary: string;
  author: string;
  category: string;
  tags: string[];
  breadcrumb: string[];
  thumbnail: string;
  description: string;
  published_at: string | null;
  og_description: string;
  _constituency_validation?: {
    valid: boolean;
    score: number;
    reason: string;
  };
}

/** Normalized article from sources/sakshi/normalizer.py. */
export interface SakshiArticle {
  id: string;
  source: 'sakshi';
  source_type: 'newspaper';
  title: string;
  content: string;
  article: string;
  summary: string;
  published_at: string;
  created_on: string;
  author: string;
  category: string;
  subcategory: string;
  tags: string[];
  keywords: string[];
  entities: string[];
  location: Record<string, never>;
  thumbnail: string;
  description: string;
  source_url: string;
  url: string;
  language: 'te';
  channel: 'Sakshi';
  constituency_score: number | null;
  constituency_match_reason: string | null;
}

export interface SakshiFilterStats {
  fetched: number;
  accepted: number;
  rejected: number;
  rejected_reasons: Record<string, number>;
  scores: number[];
}

export interface SakshiCollectorEnvelope {
  generated_at: string;
  collector: string;
  source: string;
  source_name: 'sakshi';
  total_articles: number;
  filter_stats: SakshiFilterStats;
  articles: SakshiArticle[];
}
