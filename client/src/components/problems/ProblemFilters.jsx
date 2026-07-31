function ChipSelect({ label, value, onChange, options }) {
  return (
    <div className="flex flex-col gap-1 min-w-[140px]">
      <label className="text-xs font-medium text-muted">{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="input-field !py-1.5">
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function ProblemFilters({
  priority,
  department,
  category,
  onPriorityChange,
  onDepartmentChange,
  onCategoryChange,
  departments,
  categories,
  onReset,
}) {
  return (
    <div className="card p-4 flex flex-wrap items-end gap-3">
      <ChipSelect
        label="Priority"
        value={priority}
        onChange={onPriorityChange}
        options={['High', 'Medium', 'Low']}
      />
      <ChipSelect
        label="Department"
        value={department}
        onChange={onDepartmentChange}
        options={departments}
      />
      <ChipSelect
        label="Category"
        value={category}
        onChange={onCategoryChange}
        options={categories}
      />
      <button type="button" onClick={onReset} className="btn-secondary !py-1.5 !text-sm">
        Reset
      </button>
    </div>
  );
}
