import { Link, useSearchParams } from 'react-router-dom';
import { useNewsContext } from '../context/NewsContext';
import Charts from '../components/analytics/Charts';
import KeywordBadges from '../components/analytics/KeywordBadges';
import PositiveSummaryStrip from '../components/analytics/PositiveSummaryStrip';

export default function AnalyticsPage() {
  const { stats } = useNewsContext();
  const [searchParams, setSearchParams] = useSearchParams();
  const range = searchParams.get('range') || '7d';

  const setRange = (value) => {
    setSearchParams({ range: value }, { replace: true });
  };

  const sampleTitles = (stats.positiveDevelopments || []).slice(0, 1).map((a) => a.title);

  return (
    <div className="page-enter space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="section-title text-xl">Analytics</h2>
          <p className="text-sm text-muted">Trends, breakdowns, and constituency patterns</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted">Range</span>
          <button
            type="button"
            onClick={() => setRange('7d')}
            className={`rounded-control px-3 py-1.5 text-sm font-medium transition-colors ${
              range === '7d' ? 'bg-primary text-white' : 'border border-app text-muted hover:text-app'
            }`}
          >
            7 days
          </button>
          <Link to="/news" className="text-sm font-semibold text-primary hover:underline ml-2">
            Open News →
          </Link>
        </div>
      </div>

      <PositiveSummaryStrip count={stats.positive} sampleTitles={sampleTitles} />

      <Charts stats={stats} />

      <KeywordBadges keywords={stats.topKeywords} />
    </div>
  );
}
