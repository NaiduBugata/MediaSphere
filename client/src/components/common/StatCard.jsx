import { formatPercent } from '../../utils/format';

function ChangeIndicator({ change }) {
  if (change === 0 || change === undefined || change === null) {
    return <span className="text-meta">No change since yesterday</span>;
  }
  const sign = change > 0 ? '+' : '';
  const color = change > 0 ? 'text-primary' : 'text-muted';
  return (
    <span className={`text-meta font-medium ${color}`}>
      {sign}
      {change} since yesterday
    </span>
  );
}

export default function StatCard({
  icon: Icon,
  label,
  count,
  total,
  change,
  highlight = false,
  compact = false,
}) {
  if (compact) {
    return (
      <div
        className={`card flex h-[52px] items-center gap-2.5 px-3 py-1.5 ${
          highlight ? 'bg-surface' : ''
        }`}
      >
        {Icon && (
          <div
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-control ${
              highlight ? 'bg-primary/10' : 'bg-app'
            }`}
          >
            <Icon className={`h-3.5 w-3.5 ${highlight ? 'text-primary' : 'text-muted'}`} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[9px] font-semibold uppercase tracking-[0.07em] text-muted truncate leading-none mb-0.5">
            {label}
          </p>
          <p
            className={`text-[1.5rem] font-bold tracking-tight leading-none ${
              highlight ? 'text-primary' : 'text-app'
            }`}
          >
            {count}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="card card-hover flex h-full flex-col gap-2 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-muted">
          {label}
        </span>
        {Icon && (
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-control ${
              highlight ? 'bg-primary/10' : 'bg-app'
            }`}
          >
            <Icon className={`h-4 w-4 ${highlight ? 'text-primary' : 'text-muted'}`} />
          </div>
        )}
      </div>
      <div>
        <p
          className={`text-[1.75rem] sm:text-[2rem] font-bold tracking-tight leading-none ${
            highlight ? 'text-primary' : 'text-app'
          }`}
        >
          {count}
        </p>
        <p className="mt-1.5 text-meta">{formatPercent(count, total)} of total</p>
      </div>
      <ChangeIndicator change={change} />
    </div>
  );
}
