import { Clock } from 'lucide-react';
import { Link } from 'react-router-dom';
import SourceBadge from '../common/SourceBadge';
import { formatRelativeTime } from '../../utils/format';

export default function RecentActivity({ articles, onViewDetails }) {
  if (!articles?.length) return null;
  return (
    <section aria-label="Recent activity">
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between gap-2 border-b border-app px-5 py-4">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-primary" />
            <h2 className="section-title">Recent Activity</h2>
          </div>
          <Link to="/news" className="text-xs font-semibold text-primary hover:underline">
            Browse news →
          </Link>
        </div>
        <ul className="divide-y divide-[rgb(var(--color-border))] px-5">
          {articles.map((article) => (
            <li key={article._id || article.post_id}>
              <button
                type="button"
                onClick={() => onViewDetails(article)}
                className="w-full text-left py-3 hover:text-primary transition-colors"
              >
                <div className="flex items-center gap-2 mb-1">
                  <SourceBadge source={article.source} />
                  <span className="text-xs text-muted">
                    {formatRelativeTime(article.created_on)}
                  </span>
                </div>
                <p className="text-sm font-medium text-app truncate">{article.title}</p>
                <p className="text-xs text-muted mt-0.5">
                  {article.category} · {article.sentiment}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
