import { useCallback, useMemo, useState } from 'react';
import { FiClock } from 'react-icons/fi';
import Navbar from './components/Navbar';
import SummaryCards from './components/SummaryCards';
import PriorityProblems from './components/PriorityProblems';
import ConstituencySlider from './components/ConstituencySlider';
import ActionRequired from './components/ActionRequired';
import PositiveDevelopments from './components/PositiveDevelopments';
import Charts from './components/Charts';
import Filters from './components/Filters';
import NewsTable from './components/NewsTable';
import NewsModal from './components/NewsModal';
import Spinner from './components/common/Spinner';
import ErrorState from './components/common/ErrorState';
import EmptyState from './components/common/EmptyState';
import { SkeletonCard } from './components/common/Skeleton';
import { useNews } from './hooks/useNews';
import { useFilters } from './hooks/useFilters';
import { computeStats } from './utils/stats';
import { enrichArticles } from './utils/derive';

function KeywordBadges({ keywords }) {
  if (!keywords?.length) return null;
  return (
    <section aria-label="Top keywords">
      <div className="card p-5">
        <h2 className="section-title mb-3">Top Keywords</h2>
        <div className="flex flex-wrap gap-2">
          {keywords.map(({ name, count }) => (
            <span
              key={name}
              className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary"
            >
              {name}
              <span className="text-primary/60">({count})</span>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function RecentActivity({ articles, onViewDetails }) {
  if (!articles?.length) return null;
  return (
    <section aria-label="Recent activity">
      <div className="card overflow-hidden">
        <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-4">
          <FiClock className="h-5 w-5 text-primary" />
          <h2 className="section-title">Recent Activity</h2>
        </div>
        <ul className="divide-y divide-gray-100 px-5">
          {articles.map((article) => (
            <li key={article._id || article.post_id}>
              <button
                type="button"
                onClick={() => onViewDetails(article)}
                className="w-full text-left py-3 hover:text-primary transition-colors"
              >
                <p className="text-sm font-medium text-gray-800 truncate">{article.title}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {article.category} · {article.sentiment}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default function App() {
  const { articles, loading, error, lastUpdated, refresh } = useNews();
  const enriched = useMemo(() => enrichArticles(articles), [articles]);
  const stats = useMemo(() => computeStats(enriched), [enriched]);
  const { filters, setFilter, resetFilters, filteredArticles } = useFilters(enriched);

  const [selectedArticle, setSelectedArticle] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const handleSearchChange = useCallback(
    (value) => setFilter('search', value),
    [setFilter]
  );

  const handleViewDetails = useCallback((article) => {
    setSelectedArticle(article);
    setModalOpen(true);
  }, []);

  const handleCloseModal = useCallback(() => {
    setModalOpen(false);
    setSelectedArticle(null);
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  }, [refresh]);

  if (loading && articles.length === 0) {
    return (
      <div className="min-h-screen bg-secondary">
        <div className="h-16 border-b border-gray-200 bg-white" />
        <main className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8 xl:px-12 py-6 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
          <Spinner label="Loading constituency data..." />
        </main>
      </div>
    );
  }

  if (error && articles.length === 0) {
    return (
      <div className="min-h-screen bg-secondary">
        <div className="h-16 border-b border-gray-200 bg-white" />
        <main className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8 xl:px-12 py-6">
          <ErrorState message={error} onRetry={handleRefresh} />
        </main>
      </div>
    );
  }

  if (!loading && articles.length === 0) {
    return (
      <div className="min-h-screen bg-secondary">
        <Navbar
          search={filters.search}
          onSearchChange={handleSearchChange}
          lastUpdated={lastUpdated}
          onRefresh={handleRefresh}
          refreshing={refreshing}
        />
        <main className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8 xl:px-12 py-6">
          <EmptyState
            title="No news data yet"
            message="Run the analysis pipeline to collect and categorize constituency news."
          />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary">
      <Navbar
        search={filters.search}
        onSearchChange={handleSearchChange}
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      />

      <main className="mx-auto max-w-[1600px] px-4 sm:px-6 lg:px-8 xl:px-12 py-6 space-y-8">
        <SummaryCards stats={stats} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 flex flex-col">
            <PriorityProblems
              problems={stats.actionRequired}
              counts={stats.problemPriorityCounts}
              total={stats.problems}
              onViewDetails={handleViewDetails}
            />
          </div>
          <div className="flex flex-col gap-6">
            <RecentActivity articles={stats.recentActivity} onViewDetails={handleViewDetails} />
            <ConstituencySlider stats={stats} />
          </div>
        </div>

        <ActionRequired articles={stats.actionRequired} onViewDetails={handleViewDetails} />

        <PositiveDevelopments
          articles={stats.positiveDevelopments}
          onViewDetails={handleViewDetails}
        />

        {stats.topKeywords.length > 0 && <KeywordBadges keywords={stats.topKeywords} />}

        <Charts stats={stats} />

        <Filters
          filters={filters}
          setFilter={setFilter}
          resetFilters={resetFilters}
          filterOptions={stats.filterOptions}
        />

        <NewsTable articles={filteredArticles} onViewDetails={handleViewDetails} />
      </main>

      <NewsModal
        article={selectedArticle}
        isOpen={modalOpen}
        onClose={handleCloseModal}
      />

      <footer className="border-t border-gray-200 bg-white py-4 mt-8">
        <p className="text-center text-xs text-gray-400">
          Constituency News Monitor · MediaSphere · Narasaraopet Constituency
        </p>
      </footer>
    </div>
  );
}
