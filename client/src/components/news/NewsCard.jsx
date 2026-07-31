import ArticleMedia from '../editorial/ArticleMedia';
import CategoryChip from '../common/CategoryChip';
import SentimentBadge from '../common/SentimentBadge';
import SourceBadge from '../common/SourceBadge';
import { formatDate, formatLocation, formatRelativeTime, truncate } from '../../utils/format';

export default function NewsCard({ article, onReadMore, compact = false }) {
  if (!article) return null;

  if (compact) {
    return (
      <article className="group card card-hover flex h-full flex-col overflow-hidden">
        <button
          type="button"
          onClick={() => onReadMore?.(article)}
          className="text-left flex h-full flex-col"
        >
          <ArticleMedia article={article} className="h-[88px] w-full shrink-0" alt="" zoom />
          <div className="flex flex-1 flex-col gap-1.5 p-3">
            <div className="flex flex-wrap items-center gap-1.5 min-h-[20px]">
              <CategoryChip category={article.category} />
            </div>
            <h3 className="text-[13px] font-bold text-app leading-snug line-clamp-2 min-h-[2.25rem] group-hover:text-primary transition-colors">
              {article.title}
            </h3>
            <div className="mt-auto flex items-center justify-between gap-2 pt-1">
              <SourceBadge source={article.source} />
              <span className="text-meta shrink-0">
                {formatRelativeTime(article.created_on)}
              </span>
            </div>
          </div>
        </button>
      </article>
    );
  }

  return (
    <article className="group card card-hover flex h-full flex-col overflow-hidden">
      <button
        type="button"
        onClick={() => onReadMore?.(article)}
        className="text-left flex flex-1 flex-col min-h-0"
      >
        <ArticleMedia
          article={article}
          className="aspect-[16/9] w-full h-36 sm:h-40 shrink-0"
          alt=""
          zoom
        />

        <div className="flex flex-1 flex-col gap-2.5 p-4">
          <div className="flex flex-wrap items-center gap-1.5 min-h-[24px]">
            <CategoryChip category={article.category} />
            <SentimentBadge sentiment={article.sentiment} />
          </div>

          <h3 className="text-headline text-[1.125rem] text-app line-clamp-2 min-h-[2.7rem] group-hover:text-primary transition-colors">
            {article.title}
          </h3>

          <p className="text-summary text-muted line-clamp-3 min-h-[4.4rem]">
            {article.summary ? truncate(article.summary, 140) : '\u00A0'}
          </p>

          <div className="mt-auto pt-3 space-y-1.5 border-t border-app/70">
            <div className="flex flex-wrap items-center gap-2">
              <SourceBadge source={article.source} />
              <span className="text-meta">{formatDate(article.created_on)}</span>
            </div>
            <p className="text-meta truncate">{formatLocation(article.location)}</p>
          </div>
        </div>
      </button>

      <div className="px-4 pb-4 pt-1">
        <button
          type="button"
          onClick={() => onReadMore?.(article)}
          className="w-full rounded-control border border-app bg-app px-3 py-2.5 text-[13px] font-semibold text-app hover:border-primary/30 hover:bg-primary hover:text-white transition-colors duration-200"
        >
          Read More
        </button>
      </div>
    </article>
  );
}
