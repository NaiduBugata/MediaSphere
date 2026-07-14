import { useCallback, useEffect, useMemo, useState } from 'react';
import { FiChevronDown, FiChevronUp, FiExternalLink } from 'react-icons/fi';
import SentimentBadge from './common/SentimentBadge';
import CategoryChip from './common/CategoryChip';
import SourceBadge from './common/SourceBadge';
import EmptyState from './common/EmptyState';
import { formatDate, getArticleSortTime, safeString } from '../utils/format';

const PAGE_SIZE = 10;
const SORTABLE = ['title', 'category', 'sentiment', 'created_on'];

function SortHeader({ field, label, sortField, sortDir, onSort }) {
  const active = sortField === field;
  return (
    <th
      scope="col"
      className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider cursor-pointer select-none hover:text-primary"
      onClick={() => onSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active && (sortDir === 'asc' ? <FiChevronUp className="h-3 w-3" /> : <FiChevronDown className="h-3 w-3" />)}
      </span>
    </th>
  );
}

export default function NewsTable({ articles, onViewDetails }) {
  const [page, setPage] = useState(1);
  const [sortField, setSortField] = useState('created_on');
  const [sortDir, setSortDir] = useState('desc');

  useEffect(() => {
    setPage(1);
  }, [articles]);

  const handleSort = useCallback(
    (field) => {
      if (!SORTABLE.includes(field)) return;
      if (sortField === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortField(field);
        setSortDir('asc');
      }
      setPage(1);
    },
    [sortField]
  );

  const sorted = useMemo(() => {
    return [...articles].sort((a, b) => {
      let av;
      let bv;
      if (sortField === 'created_on') {
        av = getArticleSortTime(a);
        bv = getArticleSortTime(b);
      } else {
        av = String(a[sortField] || '').toLowerCase();
        bv = String(b[sortField] || '').toLowerCase();
      }
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [articles, sortField, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const paginated = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (articles.length === 0) {
    return (
      <section aria-label="Latest news">
        <h2 className="section-title mb-4">Latest News</h2>
        <div className="card">
          <EmptyState title="No articles found" message="Try adjusting your filters or search query." />
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Latest news">
      <div className="flex items-center justify-between mb-4">
        <h2 className="section-title">Latest News</h2>
        <span className="text-sm text-gray-500">{articles.length} articles</span>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-secondary">
              <tr>
                <SortHeader field="title" label="Title" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Channel</th>
                <SortHeader field="category" label="Category" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
                <SortHeader field="sentiment" label="Sentiment" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider hidden md:table-cell">District</th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider hidden lg:table-cell">Mandal</th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider hidden lg:table-cell">Village</th>
                <SortHeader field="created_on" label="Date" sortField={sortField} sortDir={sortDir} onSort={handleSort} />
                <th scope="col" className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {paginated.map((article) => (
                <tr key={article._id || article.post_id} className="hover:bg-secondary/50 transition-colors">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900 max-w-xs">
                    <div className="flex items-start gap-2 min-w-0">
                      <SourceBadge source={article.source} />
                      <span className="truncate">{safeString(article.title, 'Untitled')}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 max-w-[140px] truncate hidden sm:table-cell">
                    {article.source === 'youtube'
                      ? safeString(article.channel, '—')
                      : article.source === 'sakshi'
                        ? safeString(article.channel, 'Sakshi')
                        : 'Lokal News'}
                  </td>
                  <td className="px-4 py-3">
                    <CategoryChip category={article.category} />
                  </td>
                  <td className="px-4 py-3">
                    <SentimentBadge sentiment={article.sentiment} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 hidden md:table-cell">
                    {safeString(article.location?.district)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 hidden lg:table-cell">
                    {safeString(article.location?.mandal)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 hidden lg:table-cell">
                    {safeString(article.location?.village)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                    {formatDate(article.created_on)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => onViewDetails(article)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                    >
                      View
                      <FiExternalLink className="h-3 w-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3">
            <p className="text-sm text-gray-500">
              Page {page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-md border border-gray-200 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-secondary transition-colors"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-md border border-gray-200 px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-secondary transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
