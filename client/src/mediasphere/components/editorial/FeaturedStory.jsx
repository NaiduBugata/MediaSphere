import { Clock } from 'lucide-react';
import ArticleMedia from './ArticleMedia';
import { formatRelativeTime, truncate } from '../../utils/format';

export default function FeaturedStory({
  article,
  onReadMore,
  badge = 'Featured Story',
  compact = false,
}) {
  if (!article) return null;

  // Compact (Dashboard): fill parent band — overlay stays lower-left.
  const height = compact ? 'h-full min-h-[240px]' : 'h-full min-h-[22rem]';

  return (
    <article
      className={`group relative overflow-hidden rounded-card border border-msline/60 bg-surface shadow-soft ${height}`}
    >
      <ArticleMedia
        article={article}
        className="absolute inset-0 h-full w-full"
        alt=""
        zoom
        preferHero
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/25 to-transparent" />

      <div
        className={`relative z-10 flex h-full flex-col justify-end items-start ${
          compact ? 'p-4 sm:p-5' : 'p-4 sm:p-5'
        }`}
      >
        <div className="w-full rounded-xl bg-black/55 p-4 backdrop-blur-[2px]">
        <span className="mb-2.5 inline-flex w-fit rounded-md bg-primary px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-white shadow-soft">
          {badge}
        </span>

        <h2
          className={`max-w-2xl font-bold leading-snug tracking-tight text-white line-clamp-2 ${
            compact ? 'text-xl sm:text-2xl' : 'text-2xl sm:text-[1.75rem]'
          }`}
        >
          {article.title}
        </h2>

        {article.summary && (
          <p
            className={`mt-2 max-w-xl text-white/90 leading-relaxed line-clamp-2 ${
              compact ? 'text-sm sm:text-[15px]' : 'text-sm sm:text-[15px]'
            }`}
          >
            {truncate(article.summary, compact ? 170 : 190)}
          </p>
        )}

        <div className={`flex flex-wrap items-center gap-3 ${compact ? 'mt-4' : 'mt-4'}`}>
          <button
            type="button"
            onClick={() => onReadMore?.(article)}
            className="btn-primary !py-2 !px-4 !text-sm shadow-soft"
          >
            Read More
          </button>
          <span className="inline-flex items-center gap-1.5 text-[12px] text-white/75">
            <Clock className="h-3.5 w-3.5" />
            {formatRelativeTime(article.created_on)}
          </span>
          {article.category && (
            <span className="text-[12px] text-white/70">{article.category}</span>
          )}
        </div>
        </div>
      </div>
    </article>
  );
}
