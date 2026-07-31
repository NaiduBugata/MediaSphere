export function PrefSection({ title, description, children }) {
  return (
    <section className="card p-5 space-y-4">
      <div>
        <h2 className="section-title">{title}</h2>
        {description ? <p className="text-sm text-muted mt-1">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function PrefField({ label, children }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}

export function PrefInput(props) {
  return (
    <input
      {...props}
      className="rounded-md border border-app bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
    />
  );
}

export function PrefToggle({ label, checked, onChange }) {
  return (
    <label className="flex items-center justify-between gap-3 rounded-md border border-app bg-secondary px-3 py-2">
      <span className="text-sm text-app">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
      />
    </label>
  );
}
