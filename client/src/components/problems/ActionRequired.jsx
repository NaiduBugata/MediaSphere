import { CircleAlert } from 'lucide-react';
import CategoryChip from '../common/CategoryChip';
import SourceBadge from '../common/SourceBadge';
import PriorityBadge from '../common/PriorityBadge';
import EmptyState from '../common/EmptyState';
import { formatDateTime, formatLocation, truncate } from '../../utils/format';

function ActionCard({ article, onViewDetails }) {
  return (
    <div className="card card-hover p-5 flex flex-col gap-3 border-l-4 border-l-primary">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-app leading-snug">{article.title}</h3>
        <PriorityBadge priority={article.priority} />
      </div>

      <div className="rounded-control bg-primary/5 border border-primary/15 p-3">
        <p className="text-xs font-semibold text-primary mb-1">AI Summary</p>
        <p className="text-sm text-app/80 leading-relaxed">{truncate(article.summary, 200)}</p>
      </div>

      {article.problemSummary && (
        <div className="rounded-control bg-app border border-app p-3">
          <p className="text-xs font-semibold text-muted mb-1">Problem Summary</p>
          <p className="text-sm text-app/80 leading-relaxed">
            {truncate(article.problemSummary, 180)}
          </p>
        </div>
      )}

      {article.recommendedAction && (
        <div className="rounded-control border border-warning/30 bg-warning/10 p-3">
          <p className="text-xs font-semibold text-warning mb-1">Recommended Action</p>
          <p className="text-sm text-app/80 leading-relaxed">
            {truncate(article.recommendedAction, 160)}
          </p>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <SourceBadge source={article.source} />
        <CategoryChip category={article.category} />
        <span className="text-xs text-muted">{formatLocation(article.location)}</span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <div className="text-xs text-muted">
          <span className="font-medium text-app">{article.department}</span>
          <span className="mx-1">·</span>
          {formatDateTime(article.created_on)}
        </div>
        <button type="button" onClick={() => onViewDetails(article)} className="btn-primary !py-1.5 !text-xs">
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
        <CircleAlert className="h-5 w-5 text-primary" />
        <h2 className="section-title">Action Required</h2>
        <span className="badge-pill bg-primary/10 text-primary">{articles.length} issues</span>
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
