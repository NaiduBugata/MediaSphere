import { Outlet } from 'react-router-dom';
import TopNav from '../components/nav/TopNav';
import NewsModal from '../components/news/NewsModal';
import Spinner from '../components/common/Spinner';
import ErrorState from '../components/common/ErrorState';
import EmptyState from '../components/common/EmptyState';
import { SkeletonCard } from '../components/common/Skeleton';
import { useNewsContext } from '../context/NewsContext';

export default function AppShell() {
  const {
    articles,
    loading,
    error,
    refresh,
    selectedArticle,
    modalOpen,
    closeArticle,
  } = useNewsContext();

  if (loading && articles.length === 0) {
    return (
      <div className="min-h-screen bg-app">
        <div className="h-[4.25rem] border-b border-app bg-navbar" />
        <main className="mx-auto max-w-none w-full px-6 py-6 space-y-6">
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
      <div className="min-h-screen bg-app">
        <div className="h-[4.25rem] border-b border-app bg-navbar" />
        <main className="mx-auto max-w-none w-full px-6 py-6">
          <ErrorState message={error} onRetry={refresh} />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-app flex flex-col">
      <TopNav />

      <main className="mx-auto w-full max-w-none flex-1 px-6 pt-6 pb-4">
        {!loading && articles.length === 0 ? (
          <EmptyState
            title="No news data yet"
            message="Run the analysis pipeline to collect and categorize constituency news."
          />
        ) : (
          <div className="page-enter h-full">
            <Outlet />
          </div>
        )}
      </main>

      <NewsModal article={selectedArticle} isOpen={modalOpen} onClose={closeArticle} />
    </div>
  );
}
