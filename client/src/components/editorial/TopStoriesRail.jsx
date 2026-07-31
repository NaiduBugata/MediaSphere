import { Link } from 'react-router-dom';
import ArticleMedia from './ArticleMedia';
import { formatRelativeTime, truncate } from '../../utils/format';

export default function TopStoriesRail({
  articles = [],
  onSelect,
  title = 'Critical Issues',
  viewAllTo = '/problems',
  dense = false,
  limit = 5,
}) {
  const items = (articles || []).slice(0, limit);

  return (
    <aside className="flex h-full flex-col rounded-card border border-app/60 bg-surface shadow-soft overflow-hidden">
      <div className="flex items-center justify-between border-b border-app/70 shrink-0 px-4 py-3">
        <h2 className="text-[15px] font-bold text-app tracking-tight">{title}</h2>
        {viewAllTo && (
          <Link
            to={viewAllTo}
            className="text-[13px] font-semibold text-primary hover:text-primary-hover transition-colors"
          >
            View all
          </Link>
        )}
      </div>

      {items.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted text-center flex-1 flex items-center justify-center">
          No items right now.
        </p>
      ) : (
        <ul className="flex-1 flex flex-col divide-y divide-[rgb(var(--color-border)/0.8)] overflow-hidden">
          {items.map((article) => (
            <li key={article._id || article.post_id} className="flex-1 min-h-0">
              <button
                type="button"
                onClick={() => onSelect?.(article)}
                className={`group flex h-full w-full items-center text-left transition-colors duration-200 hover:bg-app/80 overflow-hidden ${
                  dense ? 'gap-3 px-3.5 py-2' : 'gap-3 px-4 py-3'
                }`}
              >
                <ArticleMedia
                  article={article}
                  className={`shrink-0 rounded-control shadow-soft ${
                    dense ? 'h-11 w-11' : 'h-14 w-14'
                  }`}
                  alt=""
                  zoom
                />
                <div className="min-w-0 flex-1">
                  <p
                    className={`font-semibold text-app leading-snug group-hover:text-primary transition-colors ${
                      dense ? 'text-[13px] line-clamp-2' : 'text-sm line-clamp-2'
                    }`}
                  >
                    {truncate(article.title, dense ? 80 : 90)}
                  </p>
                  <p className="mt-0.5 text-meta truncate">
                    {formatRelativeTime(article.created_on)}
                  </p>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
