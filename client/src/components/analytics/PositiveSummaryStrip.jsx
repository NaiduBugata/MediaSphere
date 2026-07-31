import { Link } from 'react-router-dom';
import { TrendingUp } from 'lucide-react';

export default function PositiveSummaryStrip({ count, sampleTitles = [] }) {
  return (
    <section aria-label="Positive developments summary">
      <div className="card card-hover p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3">
          <TrendingUp className="h-5 w-5 text-primary shrink-0 mt-0.5" />
          <div>
            <h2 className="section-title">Positive Developments</h2>
            <p className="text-sm text-muted mt-1">
              {count} positive {count === 1 ? 'story' : 'stories'} in the current dataset.
              {sampleTitles[0] ? ` Latest: “${sampleTitles[0]}”` : ''}
            </p>
          </div>
        </div>
        <Link to="/news?sentiment=Positive" className="btn-primary shrink-0">
          View in News →
        </Link>
      </div>
    </section>
  );
}
