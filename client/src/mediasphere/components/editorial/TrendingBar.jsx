export default function TrendingBar({ items = [], dense = false }) {
  if (!items.length) return null;

  const tags = items
    .map((item) => (typeof item === 'string' ? item : item.name || item.title))
    .filter(Boolean)
    .slice(0, 10);

  if (!tags.length) return null;

  return (
    <div className="flex items-center gap-2 overflow-hidden">
      <span className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
        Trending
      </span>
      <div className="flex min-w-0 gap-1.5 overflow-hidden">
        {tags.slice(0, dense ? 4 : 6).map((tag, i) => (
          <span
            key={`${tag}-${i}`}
            className="max-w-[10rem] shrink-0 truncate rounded-full bg-surface px-2.5 py-1 text-[12px] text-app"
          >
            {tag}
          </span>
        ))}
      </div>
    </div>
  );
}
