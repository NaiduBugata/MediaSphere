import { Link } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import NewsCard from '../news/NewsCard';

export default function LatestNewsRow({
  articles = [],
  onSelect,
  title = 'Latest News',
  viewAllTo = '/news',
  columns = 4,
  compact = false,
  headerAction = null,
  showHeader = true,
}) {
  const gridCols =
    columns === 3
      ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'
      : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4';

  const list = compact ? (articles || []).slice(0, 4) : articles;

  return (
    <section aria-label={title} className="shrink-0">
      {showHeader && (
        <div className={`flex items-center justify-between gap-4 ${compact ? 'mb-3' : 'mb-4'} min-h-[36px]`}>
          <h2
            className={`section-title leading-none inline-flex items-center gap-2 ${compact ? '!text-[1.25rem]' : ''}`}
          >
            <span>{title}</span>
            <ChevronDown className="h-5 w-5 shrink-0 text-muted" aria-hidden="true" strokeWidth={2.5} />
          </h2>
          <div className="flex items-center gap-3 shrink-0">
            {headerAction}
            {!headerAction && viewAllTo && (
              <Link
                to={viewAllTo}
                className="text-[15px] font-semibold text-primary hover:text-primary-hover transition-colors"
              >
                View All →
              </Link>
            )}
          </div>
        </div>
      )}

      {list.length === 0 ? (
        <p className="text-sm text-muted py-6 text-center">No recent articles.</p>
      ) : (
        <div className={`grid items-stretch ${gridCols} ${compact ? 'gap-3' : 'gap-4'}`}>
          {list.map((article) => (
            <NewsCard
              key={article._id || article.post_id}
              article={article}
              onReadMore={onSelect}
              compact={compact}
            />
          ))}
        </div>
      )}
    </section>
  );
}
