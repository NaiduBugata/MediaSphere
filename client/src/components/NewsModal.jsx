import { FiExternalLink } from 'react-icons/fi';
import Modal from './common/Modal';
import SentimentBadge from './common/SentimentBadge';
import CategoryChip from './common/CategoryChip';
import PriorityBadge from './common/PriorityBadge';
import SourceBadge from './common/SourceBadge';
import { formatDateTime, formatLocation, isYoutubeSource, safeString } from '../utils/format';

function HighlightBlock({ title, content, variant = 'primary' }) {
  const styles =
    variant === 'primary'
      ? 'bg-primary/5 border-primary/20'
      : 'bg-gray-50 border-gray-200';
  const titleColor = variant === 'primary' ? 'text-primary' : 'text-gray-700';

  return (
    <div className={`rounded-lg border p-4 ${styles}`}>
      <p className={`text-xs font-bold uppercase tracking-wide mb-2 ${titleColor}`}>{title}</p>
      <p className="text-sm text-gray-800 leading-relaxed">{content || '—'}</p>
    </div>
  );
}

function BadgeList({ items, label }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 mb-2">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, i) => {
          const name = typeof item === 'object' ? item.name : String(item);
          const type = typeof item === 'object' ? item.type : null;
          return (
            <span
              key={`${name}-${i}`}
              className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
            >
              {name}
              {type && <span className="ml-1 text-primary/60">({type})</span>}
            </span>
          );
        })}
      </div>
    </div>
  );
}

export default function NewsModal({ article, isOpen, onClose }) {
  if (!article) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={article.title} wide>
      <div className="space-y-5">
        <HighlightBlock title="AI Summary" content={article.summary} variant="primary" />

        {article.isActionRequired && (
          <HighlightBlock title="Problem Summary" content={article.problemSummary} variant="secondary" />
        )}

        <div className="rounded-lg border border-primary/20 bg-secondary p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-primary mb-2">
            Recommended Action
          </p>
          <p className="text-sm text-gray-800 leading-relaxed">
            {article.recommendedAction || '—'}
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-gray-500 mb-1">Source</p>
            <SourceBadge source={article.source} />
          </div>
          {article.channel && (
            <div>
              <p className="text-xs text-gray-500 mb-1">Channel</p>
              <p className="text-sm font-medium text-gray-800">{article.channel}</p>
            </div>
          )}
          <div>
            <p className="text-xs text-gray-500 mb-1">Category</p>
            <CategoryChip category={article.category} />
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Subcategory</p>
            <p className="text-sm font-medium text-gray-800">{safeString(article.subcategory)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Sentiment</p>
            <SentimentBadge sentiment={article.sentiment} />
          </div>
          {article.isActionRequired && (
            <div>
              <p className="text-xs text-gray-500 mb-1">Priority</p>
              <PriorityBadge priority={article.priority} />
            </div>
          )}
          {article.isActionRequired && (
            <div className="col-span-2">
              <p className="text-xs text-gray-500 mb-1">Department Responsible</p>
              <p className="text-sm font-medium text-gray-800">{article.department}</p>
            </div>
          )}
        </div>

        <div>
          <p className="text-xs text-gray-500 mb-1">Location</p>
          <p className="text-sm text-gray-800">{formatLocation(article.location)}</p>
          {article.location?.state && (
            <p className="text-xs text-gray-500 mt-0.5">{article.location.state}</p>
          )}
        </div>

        <BadgeList items={article.keywords} label="Keywords" />
        <BadgeList items={article.entities} label="Entities" />

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-gray-100">
          <p className="text-xs text-gray-500">
            Published {formatDateTime(article.created_on)}
          </p>
          {article.source_url && (
            <a
              href={article.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 transition-colors"
            >
              Open {isYoutubeSource(article.source) ? 'YouTube Video' : 'Original Article'}
              <FiExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>
    </Modal>
  );
}
