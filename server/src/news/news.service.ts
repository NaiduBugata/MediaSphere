import { Injectable } from '@nestjs/common';
import { Document } from 'mongodb';
import { ArticleRepository } from '../database/repositories/article.repository';
import { PipelineStateRepository } from '../database/repositories/pipeline-state.repository';
import { hasAssemblySegment } from '../pipeline/native/constituency';
import {
  NormalizedArticle,
  NewsListResponse,
  NewsStatsResponse,
} from '../common/types/article';
import {
  entityDisplayName,
  falsyToDefault,
  falsyToEmptyString,
  flaskDateKey,
  parseFlaskDate,
  utcDaysBackIso,
} from '../common/utils/dates';

@Injectable()
export class NewsService {
  constructor(
    private readonly articles: ArticleRepository,
    private readonly pipelineState: PipelineStateRepository,
  ) {}

  normalizeArticle(doc: Document): NormalizedArticle {
    const locationRaw = doc.location;
    const location =
      locationRaw && typeof locationRaw === 'object' && !Array.isArray(locationRaw)
        ? (locationRaw as Record<string, unknown>)
        : {};

    const keywordsRaw = doc.keywords;
    const entitiesRaw = doc.entities;
    const tagsRaw = doc.tags;

    return {
      _id: String(doc._id ?? ''),
      post_id: doc.post_id,
      title: falsyToEmptyString(doc.title),
      summary: falsyToEmptyString(doc.summary),
      category: falsyToEmptyString(doc.category),
      subcategory: falsyToEmptyString(doc.subcategory),
      sentiment: falsyToEmptyString(doc.sentiment),
      location: {
        district: (location.district as string) ?? null,
        mandal: (location.mandal as string) ?? null,
        village: (location.village as string) ?? null,
        town: (location.town as string) ?? null,
        state: falsyToDefault(location.state, 'Andhra Pradesh'),
      },
      keywords: keywordsRaw ? (keywordsRaw as unknown[]) : [],
      entities: entitiesRaw ? (entitiesRaw as unknown[]) : [],
      problem: doc.problem ?? null,
      problem_id: doc.problem_id ?? null,
      source_url: falsyToEmptyString(doc.source_url),
      // Flask: doc.get("source") or "lokal"  — empty string becomes lokal
      source: falsyToDefault(doc.source, 'lokal'),
      channel: falsyToEmptyString(doc.channel),
      thumbnail: falsyToEmptyString(
        doc.thumbnail || doc.thumbnail_url || doc.image_url || '',
      ),
      author: falsyToEmptyString(doc.author),
      tags: tagsRaw ? (tagsRaw as unknown[]) : [],
      created_on: falsyToEmptyString(doc.created_on),
      first_seen_at: falsyToEmptyString(doc.first_seen_at),
      last_updated_at: falsyToEmptyString(doc.last_updated_at),
      assembly_segment: falsyToEmptyString(doc.assembly_segment),
    };
  }

  /** Only articles mapped to one of the seven assembly segments belong to the constituency dataset. */
  private async constituencyDocs(): Promise<Document[]> {
    return (await this.articles.findAll()).filter((doc) => hasAssemblySegment(doc));
  }

  private articleSortTimestamp(article: NormalizedArticle): number {
    for (const field of ['created_on', 'first_seen_at', 'last_updated_at'] as const) {
      const parsed = parseFlaskDate(article[field] || '');
      if (parsed) return parsed.getTime() / 1000;
    }
    return 0;
  }

  private sortNewestFirst(articles: NormalizedArticle[]): NormalizedArticle[] {
    return [...articles].sort(
      (a, b) => this.articleSortTimestamp(b) - this.articleSortTimestamp(a),
    );
  }

  async listNews(sourceFilter = 'all'): Promise<NewsListResponse> {
    const docs = await this.constituencyDocs();
    let articles = this.sortNewestFirst(docs.map((d) => this.normalizeArticle(d)));
    // Flask: (request.args.get("source") or "all").lower()
    const filter = (sourceFilter || 'all').toLowerCase();
    if (filter === 'lokal') {
      // Flask filter uses a.get("source", "lokal") == "lokal" after normalize
      articles = articles.filter((a) => (a.source || 'lokal') === 'lokal');
    } else if (filter === 'youtube') {
      articles = articles.filter((a) => a.source === 'youtube');
    } else if (filter === 'sakshi') {
      articles = articles.filter((a) => a.source === 'sakshi');
    }

    let data_revision: string | null = null;
    try {
      data_revision = await this.pipelineState.getDataRevision();
    } catch {
      data_revision = null;
    }

    return { articles, count: articles.length, data_revision };
  }

  computeStats(
    articles: NormalizedArticle[],
  ): Omit<NewsStatsResponse, 'generated_at' | 'data_revision'> {
    const countMap = (items: string[]) => {
      const m: Record<string, number> = {};
      for (const i of items) m[i] = (m[i] || 0) + 1;
      return m;
    };

    const sentiment = countMap(articles.map((a) => a.sentiment || 'Unknown'));
    const category = countMap(articles.map((a) => a.category || 'Other'));
    const district = countMap(
      articles.map((a) => a.location.district || 'Unknown'),
    );
    const mandal = countMap(articles.map((a) => a.location.mandal || 'Unknown'));
    const village = countMap(
      articles.map((a) => a.location.village || 'Unknown'),
    );
    const by_source = countMap(articles.map((a) => a.source || 'lokal'));

    const keywordCounter: Record<string, number> = {};
    const entityCounter: Record<string, number> = {};
    for (const article of articles) {
      for (const kw of article.keywords || []) {
        if (kw) {
          const key = String(kw);
          keywordCounter[key] = (keywordCounter[key] || 0) + 1;
        }
      }
      for (const entity of article.entities || []) {
        const name = entityDisplayName(entity);
        if (name) entityCounter[name] = (entityCounter[name] || 0) + 1;
      }
    }

    const topN = (counter: Record<string, number>, n: number) =>
      Object.entries(counter)
        .sort((a, b) => b[1] - a[1])
        .slice(0, n)
        .map(([name, count]) => ({ name, count }));

    // Flask: today = datetime.now(timezone.utc).date() — UTC window
    const daily_counts: Record<string, number> = {};
    for (let i = 0; i < 7; i++) {
      daily_counts[utcDaysBackIso(i)] = 0;
    }

    for (const article of articles) {
      // Flask _date_key uses offset-aware calendar date (not UTC day)
      const key =
        flaskDateKey(article.first_seen_at || '') ||
        flaskDateKey(article.created_on || '');
      if (key && key in daily_counts) daily_counts[key] += 1;
    }

    const daily_trend = Object.keys(daily_counts)
      .sort()
      .map((date) => ({ date, count: daily_counts[date] }));

    const problem_count = articles.filter((a) =>
      ['Negative', 'Problem'].includes(a.sentiment || ''),
    ).length;

    return {
      total: articles.length,
      by_source,
      sentiment,
      category,
      district,
      mandal,
      village,
      daily_trend,
      top_keywords: topN(keywordCounter, 20),
      top_entities: topN(entityCounter, 20),
      positive_count: sentiment.Positive || 0,
      negative_count: sentiment.Negative || 0,
      neutral_count: sentiment.Neutral || 0,
      statement_count: sentiment.Statement || 0,
      problem_count,
    };
  }

  async getStats(): Promise<NewsStatsResponse> {
    const docs = await this.constituencyDocs();
    const articles = docs.map((d) => this.normalizeArticle(d));
    const stats = this.computeStats(articles);
    let data_revision: string | null = null;
    try {
      data_revision = await this.pipelineState.getDataRevision();
    } catch {
      data_revision = null;
    }
    return {
      ...stats,
      generated_at: new Date().toISOString(),
      data_revision,
    };
  }
}
