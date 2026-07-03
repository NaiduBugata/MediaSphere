import { FiAlertCircle } from 'react-icons/fi';
import CategoryChip from './common/CategoryChip';
import PriorityBadge from './common/PriorityBadge';
import EmptyState from './common/EmptyState';
import { formatDateTime, formatLocation, truncate } from '../utils/format';

function ActionCard({ article, onViewDetails }) {
  return (
    <div className="card p-5 flex flex-col gap-3 border-l-4 border-l-primary">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-gray-900 leading-snug">{article.title}</h3>
        <PriorityBadge priority={article.priority} />
      </div>

      <div className="rounded-md bg-primary/5 border border-primary/10 p-3">
        <p className="text-xs font-semibold text-primary mb-1">AI Summary</p>
        <p className="text-sm text-gray-700 leading-relaxed">{truncate(article.summary, 200)}</p>
      </div>

      {article.problemSummary && (
        <div className="rounded-md bg-gray-50 border border-gray-200 p-3">
          <p className="text-xs font-semibold text-gray-600 mb-1">Problem Summary</p>
          <p className="text-sm text-gray-700 leading-relaxed">{truncate(article.problemSummary, 180)}</p>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <CategoryChip category={article.category} />
        <span className="text-xs text-gray-500">{formatLocation(article.location)}</span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <div className="text-xs text-gray-500">
          <span className="font-medium text-gray-700">{article.department}</span>
          <span className="mx-1">·</span>
          {formatDateTime(article.created_on)}
        </div>
        <button
          type="button"
          onClick={() => onViewDetails(article)}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700 transition-colors"
        >
          View Details
        </button>
      </div>
    </div>
  );
}

export default function ActionRequired({ articles, onViewDetails }) {
  return (
    <section aria-label="Action required">
      <div className="flex items-center gap-2 mb-4">
        <FiAlertCircle className="h-5 w-5 text-primary" />
        <h2 className="section-title">Action Required</h2>
        <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
          {articles.length} issues
        </span>
      </div>

      {articles.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No urgent issues today"
            message="There are no negative developments requiring immediate attention."
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {articles.map((article) => (
            <ActionCard
              key={article._id || article.post_id}
              article={article}
              onViewDetails={onViewDetails}
            />
          ))}
        </div>
      )}
    </section>
  );
}
