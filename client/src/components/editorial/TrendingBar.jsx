export default function TrendingBar({ items = [], dense = false }) {
  if (!items.length) return null;

  const text = items
    .map((item) => (typeof item === 'string' ? item : item.name || item.title))
    .filter(Boolean)
    .slice(0, 8)
    .join('  ·  ');

  if (!text) return null;

  return (
    <div
      className={`rounded-card border border-app/60 bg-surface shadow-soft shrink-0 ${
        dense ? 'px-4 py-2' : 'px-4 py-2.5'
      }`}
    >
      <p className={`text-muted truncate ${dense ? 'text-[13px]' : 'text-sm'}`}>
        <span className="font-bold text-primary mr-2">Trending</span>
        <span className="text-app/80">{text}</span>
      </p>
    </div>
  );
}
