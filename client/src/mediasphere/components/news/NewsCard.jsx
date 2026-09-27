import ArticleMedia from '../editorial/ArticleMedia';
import CategoryChip from '../common/CategoryChip';
import SentimentBadge from '../common/SentimentBadge';
import SourceBadge from '../common/SourceBadge';
import { formatDate, formatLocation, formatRelativeTime, truncate } from '../../utils/format';

export default function NewsCard({ article, onReadMore, compact = false, variant = 'poster' }) {
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

  if (variant === 'row') {
    return (
      <article className="group card card-hover overflow-hidden">
        <button
          type="button"
          onClick={() => onReadMore?.(article)}
          className="flex w-full items-stretch text-left"
        >
          <ArticleMedia article={article} className="h-28 w-36 shrink-0 sm:h-32 sm:w-44" alt="" />
          <div className="flex min-w-0 flex-1 flex-col justify-center gap-1.5 px-4 py-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <CategoryChip category={article.category} />
              <SentimentBadge sentiment={article.sentiment} />
            </div>
            <h3 className="line-clamp-2 text-[15px] font-semibold leading-snug text-app transition-colors group-hover:text-primary">
              {article.title}
            </h3>
            <p className="flex items-center gap-2 text-meta">
              <SourceBadge source={article.source} />
              <span className="truncate">{formatRelativeTime(article.created_on)}</span>
            </p>
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
        className="flex min-h-0 flex-1 flex-col text-left"
      >
        <ArticleMedia article={article} className="aspect-[16/10] w-full shrink-0" alt="" zoom />

        <div className="flex flex-1 flex-col gap-2 p-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <CategoryChip category={article.category} />
            <SentimentBadge sentiment={article.sentiment} />
          </div>

          <h3 className="line-clamp-2 text-base font-semibold leading-snug text-app transition-colors group-hover:text-primary">
            {article.title}
          </h3>

          {article.summary && (
            <p className="line-clamp-2 text-sm leading-relaxed text-msmuted">
              {truncate(article.summary, 120)}
            </p>
          )}

          <div className="mt-auto flex flex-wrap items-center gap-2 pt-2">
            <SourceBadge source={article.source} />
            <span className="text-meta">{formatDate(article.created_on)}</span>
            <span className="text-meta truncate">{formatLocation(article.location)}</span>
          </div>
        </div>
      </button>
    </article>
  );
}
