import { formatPercent } from '../../utils/format';

function ChangeIndicator({ change }) {
  if (change === 0 || change === undefined || change === null) {
    return <span className="text-xs text-gray-400">No change since yesterday</span>;
  }
  const sign = change > 0 ? '+' : '';
  const color = change > 0 ? 'text-primary' : 'text-gray-500';
  return (
    <span className={`text-xs font-medium ${color}`}>
      {sign}{change} since yesterday
    </span>
  );
}

export default function StatCard({ icon: Icon, label, count, total, change, highlight = false }) {
  return (
    <div
      className={`card p-5 sm:p-6 flex flex-col gap-3 ${
        highlight ? 'border-primary/30 ring-1 ring-primary/10' : ''
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-500">{label}</span>
        {Icon && (
          <div className="rounded-lg bg-primary/10 p-2">
            <Icon className="h-5 w-5 text-primary" />
          </div>
        )}
      </div>
      <div>
        <p className="text-3xl sm:text-4xl font-bold text-primary tracking-tight">{count}</p>
        <p className="mt-1 text-sm text-gray-500">{formatPercent(count, total)} of total</p>
      </div>
      <ChangeIndicator change={change} />
    </div>
  );
}
