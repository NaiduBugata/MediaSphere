export default function KeywordBadges({ keywords }) {
  if (!keywords?.length) return null;
  return (
    <section aria-label="Top keywords">
      <div className="card p-5">
        <h2 className="section-title mb-3">Top Keywords</h2>
        <div className="flex flex-wrap gap-2">
          {keywords.map(({ name, count }) => (
            <span key={name} className="badge-pill bg-primary/10 text-primary">
              {name}
              <span className="ml-1 text-primary/60">({count})</span>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
