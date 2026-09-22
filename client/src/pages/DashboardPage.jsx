import { useNewsContext } from '../context/NewsContext';
import { useEditorialFeed } from '../hooks/useEditorialFeed';
import TrendingBar from '../components/editorial/TrendingBar';
import FeaturedStory from '../components/editorial/FeaturedStory';
import TopStoriesRail from '../components/editorial/TopStoriesRail';
import LatestNewsRow from '../components/editorial/LatestNewsRow';
import SummaryCards from '../components/dashboard/SummaryCards';
import { ChevronDown } from 'lucide-react';

/**
 * Single-viewport desktop layout — no nested scrollers.
 * Rhythm: Trending → Hero+Rail → KPIs → Latest preview
 */
export default function DashboardPage() {
  const { articles, stats, openArticle } = useNewsContext();
  const { featured, rail, latest, trending } = useEditorialFeed(articles, stats);

  return (
    <div className="page-enter flex flex-col gap-0 lg:h-[calc(100dvh-5.25rem)] lg:max-h-[calc(100dvh-5.25rem)] lg:overflow-hidden -mt-1">
      {/* Critical Issues stops with the hero — does not extend into Latest News / Statements */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5.5fr)_minmax(280px,3.5fr)] gap-5 items-stretch shrink-0 mb-4 h-auto lg:h-[340px]">
        <div className="min-h-0 flex flex-col gap-2.5 h-auto sm:min-h-[300px] lg:h-full">
          <div className="shrink-0 w-full">
            <TrendingBar items={trending} dense />
          </div>
          <div className="min-h-0 flex-1 h-[240px] sm:h-[260px] lg:h-auto">
            <FeaturedStory
              article={featured}
              onReadMore={openArticle}
              badge={featured?.isActionRequired ? 'Executive Briefing' : 'Featured Story'}
              compact
            />
          </div>
        </div>
        <div className="min-h-0 h-[500px] sm:h-[550px] lg:h-full">
          <TopStoriesRail
            articles={rail}
            onSelect={openArticle}
            title="Critical Issues"
            viewAllTo="/problems"
            limit={5}
          />
        </div>
      </div>

      {/* Latest News + KPIs — image-column width only; below Critical Issues */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,5.5fr)_minmax(280px,3.5fr)] gap-5 shrink-0 mb-4">
        <div className="flex w-full min-w-0 items-center gap-3">
          <h2 className="section-title !text-[1.25rem] leading-none inline-flex items-center gap-1.5 shrink-0">
            <span>Latest News</span>
            <ChevronDown
              className="h-4 w-4 shrink-0 text-muted"
              aria-hidden="true"
              strokeWidth={2.5}
            />
          </h2>
          <div className="min-w-0 flex-1">
            <SummaryCards stats={stats} compact />
          </div>
        </div>
        <div className="hidden lg:block" aria-hidden="true" />
      </div>

      <div className="shrink-0 min-h-0 lg:flex-1 lg:overflow-hidden">
        <LatestNewsRow
          articles={latest.slice(0, 4)}
          onSelect={openArticle}
          title="Latest News"
          viewAllTo={null}
          columns={4}
          compact
          showHeader={false}
        />
      </div>
    </div>
  );
}
