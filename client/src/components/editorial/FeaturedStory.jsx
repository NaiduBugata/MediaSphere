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
  const height = compact
    ? 'h-full min-h-[280px]'
    : 'min-h-[260px] lg:min-h-[280px] h-[260px] lg:h-[280px]';

  return (
    <article
      className={`group relative overflow-hidden rounded-card bg-surface shadow-soft card-hover border border-app/60 ${height}`}
    >
      <ArticleMedia
        article={article}
        className="absolute inset-0 h-full w-full"
        alt=""
        zoom
        preferHero
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/50 to-black/15" />
      <div className="absolute inset-0 bg-gradient-to-r from-black/55 via-black/20 to-transparent" />

      <div
        className={`relative z-10 flex h-full flex-col justify-end items-start ${
          compact ? 'p-5 sm:p-6 lg:p-7' : 'p-5 sm:p-6'
        }`}
      >
        <span className="mb-2.5 inline-flex w-fit rounded-md bg-primary px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-white shadow-soft">
          {badge}
        </span>

        <h2
          className={`text-white max-w-2xl font-bold tracking-tight leading-snug line-clamp-2 ${
            compact
              ? 'text-[1.35rem] sm:text-[1.55rem] lg:text-[1.75rem]'
              : 'text-[1.35rem] sm:text-[1.75rem] lg:text-[2rem]'
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
    </article>
  );
}
