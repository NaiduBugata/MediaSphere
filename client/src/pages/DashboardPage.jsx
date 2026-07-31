import { Link } from 'react-router-dom';
import { useNewsContext } from '../context/NewsContext';
import { useEditorialFeed } from '../hooks/useEditorialFeed';
import TrendingBar from '../components/editorial/TrendingBar';
import FeaturedStory from '../components/editorial/FeaturedStory';
import TopStoriesRail from '../components/editorial/TopStoriesRail';
import LatestNewsRow from '../components/editorial/LatestNewsRow';
import SummaryCards from '../components/dashboard/SummaryCards';

/**
 * Single-viewport desktop layout — no nested scrollers.
 * Rhythm: Trending → Hero+Rail → KPIs → Latest preview
 */
export default function DashboardPage() {
  const { articles, stats, openArticle } = useNewsContext();
  const { featured, rail, latest, trending } = useEditorialFeed(articles, stats);

  return (
    <div className="page-enter flex flex-col gap-0 lg:h-[calc(100dvh-5.5rem)] lg:max-h-[calc(100dvh-5.5rem)] lg:overflow-hidden">
      <div className="shrink-0 mb-4">
        <TrendingBar items={trending} dense />
      </div>

      {/* Hero 70% / Critical Issues 30% — matched height, no nested scroll */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,7fr)_minmax(240px,3fr)] gap-4 items-stretch shrink-0 mb-4 h-auto lg:h-[300px]">
        <div className="min-h-0 h-[260px] sm:h-[280px] lg:h-full">
          <FeaturedStory
            article={featured}
            onReadMore={openArticle}
            badge={featured?.isActionRequired ? 'Executive Briefing' : 'Featured Story'}
            compact
          />
        </div>
        <div className="min-h-0 h-[260px] sm:h-[280px] lg:h-full">
          <TopStoriesRail
            articles={rail}
            onSelect={openArticle}
            title="Critical Issues"
            viewAllTo="/problems"
            dense
            limit={5}
          />
        </div>
      </div>

      <div className="shrink-0 mb-4">
        <SummaryCards stats={stats} compact />
      </div>

      <div className="shrink-0 min-h-0 lg:flex-1 lg:overflow-hidden">
        <LatestNewsRow
          articles={latest.slice(0, 4)}
          onSelect={openArticle}
          title="Latest News"
          viewAllTo={null}
          columns={4}
          compact
          headerAction={
            <Link to="/news" className="btn-primary !py-2 !px-4 !text-sm shrink-0">
              View All News →
            </Link>
          }
        />
      </div>
    </div>
  );
}
