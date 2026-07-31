import { Filter, X } from 'lucide-react';
import { formatSourceLabel } from '../../utils/format';

const VISIBLE_KEYS = [
  'source',
  'subcategory',
  'sentiment',
  'mandal',
  'village',
  'dateFrom',
  'dateTo',
];

const CONSTITUENCY_OPTIONS = [
  'Pedakurapadu',
  'Chilakaluripet',
  'Narasaraopet',
  'Sattenapalle',
  'Vinukonda',
  'Gurazala',
  'Macherla',
];

function FilterSelect({ label, value, onChange, options, formatOption, disabled = false }) {
  return (
    <div className="flex min-w-[7.5rem] flex-1 flex-col gap-1">
      <label className="text-[10px] font-semibold uppercase tracking-wide text-muted whitespace-nowrap">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="input-field h-9 !rounded-control !py-0 !px-2.5 !text-sm leading-none disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {formatOption ? formatOption(opt) : opt}
          </option>
        ))}
      </select>
    </div>
  );
}

function FilterDate({ label, value, onChange }) {
  return (
    <div className="flex min-w-[8.5rem] flex-1 flex-col gap-1">
      <label className="text-[10px] font-semibold uppercase tracking-wide text-muted whitespace-nowrap">
        {label}
      </label>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-field h-9 !rounded-control !py-0 !px-2.5 !text-sm leading-none"
      />
    </div>
  );
}

export default function Filters({ filters, setFilter, resetFilters, filterOptions }) {
  const hasActive = VISIBLE_KEYS.some((key) => Boolean(filters[key]));

  return (
    <section
      aria-label="News filters"
      className="rounded-card border border-app/70 bg-surface px-3 py-2.5 shadow-soft"
    >
      <div className="flex items-end gap-2">
        <div className="hidden sm:flex items-center gap-1.5 pb-2 shrink-0">
          <Filter className="h-3.5 w-3.5 text-primary" />
        </div>

        {/* Desktop: single row · tablet/mobile: wrap or scroll */}
        <div className="flex min-w-0 flex-1 items-end gap-2 overflow-x-auto pb-0.5 flex-wrap lg:flex-nowrap lg:overflow-visible">
          <FilterSelect
            label="Source"
            value={filters.source}
            onChange={(v) => setFilter('source', v)}
            options={filterOptions.sources || []}
            formatOption={(v) => formatSourceLabel(v)}
          />
          <FilterSelect
            label="Subcategory"
            value={filters.subcategory}
            onChange={(v) => setFilter('subcategory', v)}
            options={filterOptions.subcategories || []}
          />
          <FilterSelect
            label="Sentiment"
            value={filters.sentiment}
            onChange={(v) => setFilter('sentiment', v)}
            options={filterOptions.sentiments || []}
          />
          <FilterSelect
            label="Mandal"
            value={filters.mandal}
            onChange={(v) => setFilter('mandal', v)}
            options={filterOptions.mandals || []}
          />
          <FilterSelect
            label="Constituency"
            value={filters.village}
            onChange={(v) => setFilter('village', v)}
            options={CONSTITUENCY_OPTIONS}
          />
          <FilterDate
            label="From"
            value={filters.dateFrom}
            onChange={(v) => setFilter('dateFrom', v)}
          />
          <FilterDate
            label="To"
            value={filters.dateTo}
            onChange={(v) => setFilter('dateTo', v)}
          />
        </div>

        {hasActive && (
          <button
            type="button"
            onClick={resetFilters}
            className="mb-0.5 inline-flex h-9 shrink-0 items-center gap-1 rounded-control px-2.5 text-[12px] font-semibold text-primary hover:bg-primary/5 transition-colors"
            title="Clear filters"
          >
            <X className="h-3.5 w-3.5" />
            <span className="hidden xl:inline">Clear</span>
          </button>
        )}
      </div>
    </section>
  );
}
