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

const STATUS_STYLES = {
  ok: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30',
  failed: 'bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/30',
  disabled: 'bg-slate-500/15 text-slate-600 dark:text-slate-300 border-slate-500/30',
  unknown: 'bg-amber-500/15 text-amber-800 dark:text-amber-200 border-amber-500/30',
};

const STATUS_LABELS = {
  ok: 'OK',
  failed: 'Failed',
  disabled: 'Disabled',
  unknown: 'Unknown',
};

export function StatusBadge({ status }) {
  const key = STATUS_STYLES[status] ? status : 'unknown';
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${STATUS_STYLES[key]}`}
    >
      {STATUS_LABELS[key]}
    </span>
  );
}

export function DeliveryStatusRow({ label, channel }) {
  if (!channel) {
    return (
      <div className="flex items-start justify-between gap-3 rounded-md border border-app bg-secondary px-3 py-2.5">
        <div>
          <p className="text-sm font-medium text-app">{label}</p>
          <p className="text-xs text-muted mt-0.5">Loading…</p>
        </div>
        <StatusBadge status="unknown" />
      </div>
    );
  }

  const parts = [];
  if (channel.last_at) {
    try {
      parts.push(`Last: ${new Date(channel.last_at).toLocaleString('en-IN')}`);
    } catch {
      parts.push(`Last: ${channel.last_at}`);
    }
  }
  if (channel.pending_articles > 0) {
    parts.push(`${channel.pending_articles} pending`);
  }
  if (channel.status === 'failed' && channel.last_error) {
    parts.push(String(channel.last_error).slice(0, 120));
  } else if (!channel.enabled) {
    parts.push('Channel off in server env');
  } else if (!channel.configured) {
    parts.push('Missing credentials or recipients');
  } else if (channel.status === 'unknown') {
    parts.push('No delivery recorded yet');
  } else if (channel.status === 'ok') {
    parts.push('Last delivery succeeded');
  }

  const daily = channel.last_daily_report;
  if (daily?.status) {
    parts.push(`Daily report: ${daily.status}${daily.report_date ? ` (${daily.report_date})` : ''}`);
  }

  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-app bg-secondary px-3 py-2.5">
      <div className="min-w-0">
        <p className="text-sm font-medium text-app">{label}</p>
        <p className="text-xs text-muted mt-0.5 break-words">{parts.join(' · ') || '—'}</p>
      </div>
      <StatusBadge status={channel.status} />
    </div>
  );
}
