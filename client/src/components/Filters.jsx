import { FiFilter, FiX } from 'react-icons/fi';

function FilterSelect({ label, value, onChange, options, formatOption }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-500">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
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
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-gray-500">{label}</label>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      />
    </div>
  );
}

export default function Filters({ filters, setFilter, resetFilters, filterOptions }) {
  const hasActive = Object.values(filters).some(Boolean);

  return (
    <section aria-label="Filters">
      <div className="card p-4 sm:p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FiFilter className="h-4 w-4 text-primary" />
            <h2 className="section-title">Filters</h2>
          </div>
          {hasActive && (
            <button
              type="button"
              onClick={resetFilters}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              <FiX className="h-3 w-3" />
              Clear all
            </button>
          )}
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-9 gap-3">
          <FilterSelect
            label="Source"
            value={filters.source}
            onChange={(v) => setFilter('source', v)}
            options={filterOptions.sources}
            formatOption={(v) => (v === 'youtube' ? 'YouTube' : v === 'lokal' ? 'Lokal' : v)}
          />
          <FilterSelect
            label="Category"
            value={filters.category}
            onChange={(v) => setFilter('category', v)}
            options={filterOptions.categories}
          />
          <FilterSelect
            label="Subcategory"
            value={filters.subcategory}
            onChange={(v) => setFilter('subcategory', v)}
            options={filterOptions.subcategories}
          />
          <FilterSelect
            label="Sentiment"
            value={filters.sentiment}
            onChange={(v) => setFilter('sentiment', v)}
            options={filterOptions.sentiments}
          />
          <FilterSelect
            label="District"
            value={filters.district}
            onChange={(v) => setFilter('district', v)}
            options={filterOptions.districts}
          />
          <FilterSelect
            label="Mandal"
            value={filters.mandal}
            onChange={(v) => setFilter('mandal', v)}
            options={filterOptions.mandals}
          />
          <FilterSelect
            label="Village"
            value={filters.village}
            onChange={(v) => setFilter('village', v)}
            options={filterOptions.villages}
          />
          <FilterDate
            label="From Date"
            value={filters.dateFrom}
            onChange={(v) => setFilter('dateFrom', v)}
          />
          <FilterDate
            label="To Date"
            value={filters.dateTo}
            onChange={(v) => setFilter('dateTo', v)}
          />
        </div>
      </div>
    </section>
  );
}
