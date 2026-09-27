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
    <aside className="flex h-full flex-col overflow-hidden rounded-card border border-msline/60 bg-surface shadow-soft">
      <div className="flex items-center justify-between border-b border-msline/70 shrink-0 px-4 py-3">
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
        <p className="px-4 py-6 text-sm text-msmuted text-center flex-1 flex items-center justify-center">
          No items right now.
        </p>
      ) : (
        <ul className="divide-y divide-msline/80">
          {items.map((article) => (
            <li key={article._id || article.post_id}>
              <button
                type="button"
                onClick={() => onSelect?.(article)}
                className="group flex w-full items-center gap-3 overflow-hidden px-3 py-2.5 text-left transition-colors duration-200 hover:bg-msbg/80"
              >
                <ArticleMedia
                  article={article}
                  className="h-14 w-14 shrink-0 rounded-lg"
                  alt=""
                />
                <div className="min-w-0 flex-1">
                  <p
                    className={`font-semibold text-app leading-snug group-hover:text-primary transition-colors ${
                      dense ? 'text-[13px] line-clamp-2' : 'text-sm line-clamp-2'
                    }`}
                  >
                    {truncate(article.title, dense ? 80 : 90)}
                  </p>
                  <p className="mt-1 text-meta truncate">
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
