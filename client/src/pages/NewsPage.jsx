import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useNewsContext } from '../context/NewsContext';
import { useFilters } from '../hooks/useFilters';
import { useEditorialFeed } from '../hooks/useEditorialFeed';
import Filters from '../components/news/Filters';
import NewsTable from '../components/news/NewsTable';
import NewsCardGrid from '../components/news/NewsCardGrid';
import NewsViewToggle from '../components/news/NewsViewToggle';
import TrendingBar from '../components/editorial/TrendingBar';
import FeaturedStory from '../components/editorial/FeaturedStory';
import TopStoriesRail from '../components/editorial/TopStoriesRail';
import LatestNewsRow from '../components/editorial/LatestNewsRow';

const QUERY_MAP = {
  q: 'search',
  source: 'source',
  category: 'category',
  sentiment: 'sentiment',
  priority: 'priority',
  district: 'district',
  mandal: 'mandal',
  village: 'village',
  from: 'dateFrom',
  to: 'dateTo',
};

const VIEW_KEY = 'mediasphere.news.view';

export default function NewsPage() {
  const { articles, stats, openArticle } = useNewsContext();
  const { filters, setFilter, resetFilters, filteredArticles } = useFilters(articles);
  const [searchParams] = useSearchParams();
  const [view, setView] = useState(() => {
    try {
      return localStorage.getItem(VIEW_KEY) === 'table' ? 'table' : 'card';
    } catch {
      return 'card';
    }
  });

  const { featured, rail, latest, trending } = useEditorialFeed(filteredArticles, {
    ...stats,
    actionRequired: filteredArticles.filter((a) => a.isActionRequired).slice(0, 10),
    topKeywords: stats.topKeywords,
  });

  useEffect(() => {
    Object.entries(QUERY_MAP).forEach(([param, key]) => {
      const value = searchParams.get(param);
      if (value != null && value !== '') {
        setFilter(key, value);
      }
    });
  }, [searchParams, setFilter]);

  const handleViewChange = (next) => {
    setView(next);
    try {
      localStorage.setItem(VIEW_KEY, next);
    } catch {
      // ignore
    }
  };

  const heroIds = new Set(
    [featured, ...rail, ...latest]
      .filter(Boolean)
      .map((a) => a._id || a.post_id)
  );
  const rest = filteredArticles.filter((a) => !heroIds.has(a._id || a.post_id));

  return (
    <div className="page-enter space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="section-title">News</h2>
          <p className="text-meta mt-1">Constituency coverage</p>
        </div>
        <NewsViewToggle value={view} onChange={handleViewChange} />
      </div>

      <Filters
        filters={filters}
        setFilter={setFilter}
        resetFilters={resetFilters}
        filterOptions={stats.filterOptions}
        articles={articles}
      />

      {view === 'card' ? (
        <>
          <TrendingBar items={trending} />

          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,7fr)_minmax(240px,3fr)] gap-4 lg:gap-5">
            <div>
              <FeaturedStory
                article={featured}
                onReadMore={openArticle}
                badge={featured?.isActionRequired ? 'Critical Briefing' : 'Featured Story'}
              />
            </div>
            <TopStoriesRail
              articles={rail}
              onSelect={openArticle}
              title="Top Stories"
              viewAllTo="/problems"
            />
          </div>

          <LatestNewsRow
            articles={latest}
            onSelect={openArticle}
            title="Latest News"
            viewAllTo={null}
            columns={3}
          />

          {rest.length > 0 && (
            <NewsCardGrid articles={rest} onViewDetails={openArticle} />
          )}
        </>
      ) : (
        <NewsTable articles={filteredArticles} onViewDetails={openArticle} />
      )}
    </div>
  );
}
