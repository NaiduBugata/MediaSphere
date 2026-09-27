import { NewsService } from './news.service';
import { Document } from 'mongodb';
import { utcDaysBackIso } from '../common/utils/dates';

describe('NewsService normalization + stats (Flask parity)', () => {
  const service = new NewsService({} as never, {} as never);

  it('normalizes empty/null/missing source to lokal', () => {
    expect(service.normalizeArticle({ source: '' } as Document).source).toBe(
      'lokal',
    );
    expect(service.normalizeArticle({ source: null } as Document).source).toBe(
      'lokal',
    );
    expect(service.normalizeArticle({} as Document).source).toBe('lokal');
    expect(
      service.normalizeArticle({ source: 'youtube' } as Document).source,
    ).toBe('youtube');
    expect(
      service.normalizeArticle({ source: 'sakshi' } as Document).source,
    ).toBe('sakshi');
    expect(
      service.normalizeArticle({ source: 'lokal' } as Document).source,
    ).toBe('lokal');
  });

  it('daily_trend uses offset calendar date at IST midnight boundary', () => {
    const today = utcDaysBackIso(0);
    const yesterday = utcDaysBackIso(1);
    // 00:30 IST on `today` == previous calendar day 19:00 UTC
    const article = service.normalizeArticle({
      title: 'boundary',
      sentiment: 'Neutral',
      source: 'lokal',
      first_seen_at: today + 'T00:30:00+05:30',
      location: {},
    } as Document);

    const stats = service.computeStats([article]);
    const map = Object.fromEntries(
      stats.daily_trend.map((d) => [d.date, d.count]),
    );

    expect(map[today]).toBe(1);
    // UTC bucketing would have placed this on yesterday — must NOT
    expect(map[yesterday] || 0).toBe(0);
  });

  it('computeStats source counts use lokal for empty sources', () => {
    const articles = [
      service.normalizeArticle({ source: '', sentiment: 'Positive' } as Document),
      service.normalizeArticle({
        source: 'youtube',
        sentiment: 'Negative',
      } as Document),
    ];
    const stats = service.computeStats(articles);
    expect(stats.by_source.lokal).toBe(1);
    expect(stats.by_source.youtube).toBe(1);
    expect(stats.positive_count).toBe(1);
    expect(stats.negative_count).toBe(1);
  });
});
