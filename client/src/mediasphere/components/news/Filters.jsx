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
    <label className="inline-flex items-center gap-1.5">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="h-8 max-w-[11rem] rounded-lg border border-msline bg-surface px-2 text-[13px] text-app disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">{label}</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {formatOption ? formatOption(opt) : opt}
          </option>
        ))}
      </select>
    </label>
  );
}

function FilterDate({ label, value, onChange }) {
  return (
    <label className="inline-flex items-center gap-1.5">
      <span className="text-[12px] text-msmuted">{label}</span>
      <input
        type="date"
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 rounded-lg border border-msline bg-surface px-2 text-[13px] text-app"
      />
    </label>
  );
}

export default function Filters({ filters, setFilter, resetFilters, filterOptions }) {
  const hasActive = VISIBLE_KEYS.some((key) => Boolean(filters[key]));

  return (
    <section aria-label="News filters" className="flex flex-wrap items-center gap-2">
      <Filter className="h-4 w-4 shrink-0 text-msmuted" aria-hidden="true" />
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
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
          className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-[13px] font-semibold text-primary hover:bg-primary/10"
        >
          <X className="h-3.5 w-3.5" />
          Clear
        </button>
      )}
    </section>
  );
}
