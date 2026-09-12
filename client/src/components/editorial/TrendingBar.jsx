export default function TrendingBar({ items = [], dense = false }) {
  if (!items.length) return null;

  const tags = items
    .map((item) => (typeof item === 'string' ? item : item.name || item.title))
    .filter(Boolean)
    .slice(0, 10);

  if (!tags.length) return null;

  return (
    <div
      className={`rounded-card border border-app/60 bg-surface shadow-soft shrink-0 flex items-center ${
        dense ? 'min-h-[3.25rem] px-5 py-3' : 'min-h-[4.5rem] px-5 py-4 sm:min-h-[5rem] sm:px-6 sm:py-5'
      }`}
    >
      <div className={`w-full ${dense ? 'text-[14px]' : 'text-[15px] sm:text-base'} leading-relaxed`}>
        <span className="font-bold text-primary mr-3 shrink-0">Trending</span>
        <span className="text-app/85">
          {tags.map((tag, i) => (
            <span key={`${tag}-${i}`}>
              {i > 0 ? <span className="mx-2 text-muted">·</span> : null}
              <span>{tag}</span>
            </span>
          ))}
        </span>
      </div>
    </div>
  );
}
