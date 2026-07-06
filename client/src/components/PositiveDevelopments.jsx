import { FiTrendingUp } from 'react-icons/fi';
import CategoryChip from './common/CategoryChip';
import SourceBadge from './common/SourceBadge';
import EmptyState from './common/EmptyState';
import { formatDate, formatLocation, truncate } from '../utils/format';

function PositiveCard({ article, onViewDetails }) {
  return (
    <div
      className="card p-4 flex flex-col gap-2 cursor-pointer hover:border-primary/30 transition-colors"
      onClick={() => onViewDetails(article)}
      onKeyDown={(e) => e.key === 'Enter' && onViewDetails(article)}
      role="button"
      tabIndex={0}
    >
      <h3 className="text-sm font-semibold text-gray-900 leading-snug">{article.title}</h3>
      <p className="text-sm text-gray-600 leading-relaxed">{truncate(article.summary, 140)}</p>
      <div className="flex flex-wrap items-center gap-2 mt-1">
        <SourceBadge source={article.source} />
        <CategoryChip category={article.category} />
        <span className="text-xs text-gray-500">{formatLocation(article.location)}</span>
        <span className="text-xs text-gray-400">{formatDate(article.created_on)}</span>
      </div>
    </div>
  );
}

export default function PositiveDevelopments({ articles, onViewDetails }) {
  return (
    <section aria-label="Positive developments">
      <div className="flex items-center gap-2 mb-4">
        <FiTrendingUp className="h-5 w-5 text-primary" />
        <h2 className="section-title">Positive Developments</h2>
      </div>

      {articles.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No positive news"
            message="No positive developments have been recorded in the current period."
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {articles.map((article) => (
            <PositiveCard
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
