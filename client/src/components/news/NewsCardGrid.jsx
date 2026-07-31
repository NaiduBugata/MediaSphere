import { useCallback, useEffect, useMemo, useState } from 'react';
import NewsCard from './NewsCard';
import EmptyState from '../common/EmptyState';
import { getArticleSortTime } from '../../utils/format';

const PAGE_SIZE = 9;

export default function NewsCardGrid({ articles, onViewDetails }) {
  const [page, setPage] = useState(1);
  const [sortField, setSortField] = useState('created_on');

  useEffect(() => {
    setPage(1);
  }, [articles]);

  const sorted = useMemo(() => {
    return [...articles].sort((a, b) => {
      if (sortField === 'created_on') {
        return getArticleSortTime(b) - getArticleSortTime(a);
      }
      const av = String(a[sortField] || '').toLowerCase();
      const bv = String(b[sortField] || '').toLowerCase();
      if (av < bv) return -1;
      if (av > bv) return 1;
      return 0;
    });
  }, [articles, sortField]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const paginated = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleSort = useCallback((e) => {
    setSortField(e.target.value);
    setPage(1);
  }, []);

  if (articles.length === 0) {
    return (
      <div className="card">
        <EmptyState title="No articles found" message="Try adjusting your filters or search query." />
      </div>
    );
  }

  return (
    <section aria-label="All news" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">{articles.length} articles</p>
        <label className="flex items-center gap-2 text-sm text-muted">
          Sort
          <select value={sortField} onChange={handleSort} className="input-field !w-auto !py-1.5">
            <option value="created_on">Newest</option>
            <option value="title">Title</option>
            <option value="category">Category</option>
            <option value="sentiment">Sentiment</option>
          </select>
        </label>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {paginated.map((article) => (
          <NewsCard
            key={article._id || article.post_id}
            article={article}
            onReadMore={onViewDetails}
          />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-sm text-muted">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="btn-secondary !py-1.5 !text-sm disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="btn-secondary !py-1.5 !text-sm disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
