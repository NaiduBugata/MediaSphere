import { Link } from 'react-router-dom';
import ArticleMedia from '../editorial/ArticleMedia';
import { formatRelativeTime, truncate } from '../../utils/format';

/**
 * Compact Critical Issues panel for the empty right slot beside the KPI row.
 * Height is fixed by the parent to match the Statements / stats cards.
 */
export default function CriticalIssuesSlot({
  articles = [],
  onSelect,
  viewAllTo = '/problems',
  totalCount,
}) {
  const items = (articles || []).slice(0, 4);

  return (
    <aside
      aria-label="Critical issues"
      className="flex h-full w-full overflow-hidden rounded-card border border-msline/60 bg-surface shadow-soft"
    >
      <div className="flex w-full min-w-0 items-center gap-2 px-2.5">
        <div className="shrink-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-primary leading-none">
            Critical
          </p>
          {viewAllTo ? (
            <Link
              to={viewAllTo}
              className="text-[10px] font-semibold text-msmuted hover:text-primary transition-colors"
            >
              View all
            </Link>
          ) : null}
        </div>

        <div className="h-7 w-px shrink-0 bg-[rgb(var(--color-border)/0.8)]" aria-hidden="true" />

        {items.length === 0 ? (
          <p className="min-w-0 flex-1 truncate text-[11px] text-msmuted">
            {totalCount > 0
              ? `${totalCount} open — see View all`
              : 'No critical issues detected'}
          </p>
        ) : (
          <ul className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto">
            {items.map((article) => (
              <li key={article._id || article.post_id} className="min-w-0 shrink-0 max-w-[42%]">
                <button
                  type="button"
                  onClick={() => onSelect?.(article)}
                  className="group flex max-w-full items-center gap-1.5 rounded-control px-1 py-0.5 text-left transition-colors hover:bg-msbg/80"
                >
                  <ArticleMedia
                    article={article}
                    className="h-7 w-7 shrink-0 rounded-control"
                    alt=""
                    zoom
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-[11px] font-semibold leading-tight text-app group-hover:text-primary">
                      {truncate(article.title, 42)}
                    </span>
                    <span className="block truncate text-[9px] text-msmuted">
                      {formatRelativeTime(article.created_on)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
