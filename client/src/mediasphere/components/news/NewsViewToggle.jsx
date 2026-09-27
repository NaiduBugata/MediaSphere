import { Grid3X3, List } from 'lucide-react';

export default function NewsViewToggle({ value, onChange }) {
  return (
    <div
      className="inline-flex rounded-control border border-msline bg-surface p-0.5 shadow-soft"
      role="group"
      aria-label="View mode"
    >
      <button
        type="button"
        onClick={() => onChange('card')}
        className={`inline-flex items-center gap-1.5 rounded-[10px] px-3 py-1.5 text-xs font-semibold transition-colors duration-200 ${
          value === 'card' ? 'bg-primary text-white' : 'text-msmuted hover:text-app hover:bg-msbg'
        }`}
      >
        <Grid3X3 className="h-3.5 w-3.5" />
        Cards
      </button>
      <button
        type="button"
        onClick={() => onChange('table')}
        className={`inline-flex items-center gap-1.5 rounded-[10px] px-3 py-1.5 text-xs font-semibold transition-colors duration-200 ${
          value === 'table' ? 'bg-primary text-white' : 'text-msmuted hover:text-app hover:bg-msbg'
        }`}
      >
        <List className="h-3.5 w-3.5" />
        Table
      </button>
    </div>
  );
}
