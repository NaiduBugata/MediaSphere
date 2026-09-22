export default function TrendingBar({ items = [], dense = false }) {
  if (!items.length) return null;

  const tags = items
    .map((item) => (typeof item === 'string' ? item : item.name || item.title))
    .filter(Boolean)
    .slice(0, 10);

  if (!tags.length) return null;

  return (
    <div
      className={`w-full rounded-card border border-app/60 bg-surface shadow-soft shrink-0 flex items-center overflow-hidden ${
        dense ? 'px-4 py-1.5' : 'px-4 py-2'
      }`}
    >
      <p
        className={`w-full min-w-0 truncate leading-none ${
          dense ? 'text-[13px]' : 'text-sm'
        }`}
      >
        <span className="font-bold text-primary mr-2">Trending</span>
        <span className="text-app/80">
          {tags.map((tag, i) => (
            <span key={`${tag}-${i}`}>
              {i > 0 ? <span className="text-muted"> · </span> : null}
              {tag}
            </span>
          ))}
        </span>
      </p>
    </div>
  );
}
