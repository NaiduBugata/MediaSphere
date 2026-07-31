import { TriangleAlert } from 'lucide-react';

const PRIORITY_DOT = {
  High: 'bg-primary',
  Medium: 'bg-primary/40',
  Low: 'bg-muted',
};

function Pill({ label, count, active, onClick, dotClass }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-2 rounded-control border px-3 py-2 text-left transition-colors duration-200 ${
        active
          ? 'border-primary bg-primary/5'
          : 'border-app bg-surface hover:border-primary/40'
      }`}
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${dotClass}`} aria-hidden="true" />
      <span className="text-xs font-medium text-muted">{label}</span>
      <span className="ml-auto text-sm font-bold text-primary">{count}</span>
    </button>
  );
}

export default function PrioritySummary({ counts, total, priorityFilter, onPriorityChange }) {
  const priorityCounts = counts || { High: 0, Medium: 0, Low: 0 };

  return (
    <section aria-label="Priority summary">
      <div className="flex items-center gap-2 mb-3">
        <TriangleAlert className="h-5 w-5 text-primary" />
        <h2 className="section-title">Problems Queue</h2>
        <span className="badge-pill bg-primary/10 text-primary">{total} total</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Pill
          label="High"
          count={priorityCounts.High}
          dotClass={PRIORITY_DOT.High}
          active={priorityFilter === 'High'}
          onClick={() => onPriorityChange(priorityFilter === 'High' ? '' : 'High')}
        />
        <Pill
          label="Medium"
          count={priorityCounts.Medium}
          dotClass={PRIORITY_DOT.Medium}
          active={priorityFilter === 'Medium'}
          onClick={() => onPriorityChange(priorityFilter === 'Medium' ? '' : 'Medium')}
        />
        <Pill
          label="Low"
          count={priorityCounts.Low}
          dotClass={PRIORITY_DOT.Low}
          active={priorityFilter === 'Low'}
          onClick={() => onPriorityChange(priorityFilter === 'Low' ? '' : 'Low')}
        />
      </div>
    </section>
  );
}
