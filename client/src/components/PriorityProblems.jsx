import { FiAlertTriangle } from 'react-icons/fi';
import CategoryChip from './common/CategoryChip';
import EmptyState from './common/EmptyState';
import { formatLocation, formatRelativeTime, truncate } from '../utils/format';

const PRIORITY_DOT = {
  High: 'bg-primary',
  Medium: 'bg-primary/40',
  Low: 'bg-gray-300',
};

function PriorityPill({ label, count, dotClass }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-secondary px-3 py-2">
      <span className={`h-2 w-2 shrink-0 rounded-full ${dotClass}`} aria-hidden="true" />
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <span className="ml-auto text-sm font-bold text-primary">{count}</span>
    </div>
  );
}

function ProblemRow({ article, onViewDetails }) {
  const isHigh = article.priority === 'High';
  const dotClass = PRIORITY_DOT[article.priority] || PRIORITY_DOT.Low;

  return (
    <button
      type="button"
      onClick={() => onViewDetails(article)}
      className={`group w-full text-left px-4 py-3.5 transition-colors hover:bg-secondary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset ${
        isHigh ? 'border-l-2 border-l-primary bg-primary/[0.02]' : 'border-l-2 border-l-transparent'
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dotClass}`}
          aria-label={`${article.priority} priority`}
        />
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-sm font-medium text-gray-900 leading-snug group-hover:text-primary transition-colors">
            {truncate(article.title, 90)}
          </p>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <CategoryChip category={article.category} />
            <span className="text-xs text-gray-400">·</span>
            <span className="text-xs text-gray-500">{formatLocation(article.location)}</span>
            <span className="text-xs text-gray-400">·</span>
            <span className="text-xs text-gray-400">{formatRelativeTime(article.created_on)}</span>
          </div>
        </div>
        <span className="hidden sm:inline shrink-0 text-xs font-semibold text-gray-400 group-hover:text-primary transition-colors">
          View →
        </span>
      </div>
    </button>
  );
}

export default function PriorityProblems({ problems, counts, total, onViewDetails }) {
  const topProblems = (problems || []).slice(0, 6);
  const priorityCounts = counts || { High: 0, Medium: 0, Low: 0 };

  return (
    <section aria-label="Priority problems" className="flex-1 flex flex-col">
      <div className="card overflow-hidden flex-1 flex flex-col">
        <div className="flex items-center justify-between gap-3 border-b border-gray-100 px-5 py-4">
          <div className="flex items-center gap-2">
            <FiAlertTriangle className="h-5 w-5 text-primary" />
            <h2 className="section-title">Priority Problems</h2>
          </div>
          <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
            {total} total
          </span>
        </div>

        {total === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <EmptyState
              title="No problems flagged"
              message="There are no negative developments requiring attention in the current period."
            />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-2 border-b border-gray-100 px-5 py-3 shrink-0">
              <PriorityPill label="High" count={priorityCounts.High} dotClass={PRIORITY_DOT.High} />
              <PriorityPill label="Medium" count={priorityCounts.Medium} dotClass={PRIORITY_DOT.Medium} />
              <PriorityPill label="Low" count={priorityCounts.Low} dotClass={PRIORITY_DOT.Low} />
            </div>

            <p className="px-5 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400 shrink-0">
              Top issues requiring attention
            </p>

            <div className="flex-1 divide-y divide-gray-100">
              {topProblems.map((article) => (
                <ProblemRow
                  key={article._id || article.post_id}
                  article={article}
                  onViewDetails={onViewDetails}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
