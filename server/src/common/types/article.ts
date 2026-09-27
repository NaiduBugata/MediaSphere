export interface ArticleLocation {
  district: string | null;
  mandal: string | null;
  village: string | null;
  town: string | null;
  state: string;
}

export interface NormalizedArticle {
  _id: string;
  post_id: unknown;
  title: string;
  summary: string;
  category: string;
  subcategory: string;
  sentiment: string;
  location: ArticleLocation;
  keywords: unknown[];
  entities: unknown[];
  problem: unknown;
  problem_id: unknown;
  source_url: string;
  source: string;
  channel: string;
  thumbnail: string;
  author: string;
  tags: unknown[];
  created_on: string;
  first_seen_at: string;
  last_updated_at: string;
}

export interface NewsListResponse {
  articles: NormalizedArticle[];
  count: number;
  data_revision: string | null;
  error?: string;
}

export interface NewsStatsResponse {
  total: number;
  by_source: Record<string, number>;
  sentiment: Record<string, number>;
  category: Record<string, number>;
  district: Record<string, number>;
  mandal: Record<string, number>;
  village: Record<string, number>;
  daily_trend: Array<{ date: string; count: number }>;
  top_keywords: Array<{ name: string; count: number }>;
  top_entities: Array<{ name: string; count: number }>;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  statement_count: number;
  problem_count: number;
  generated_at: string;
  data_revision: string | null;
  error?: string;
}
