import { getCategoryColor } from '../../utils/format';

export default function CategoryChip({ category }) {
  const colorClass = getCategoryColor(category);
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${colorClass}`}>
      {category || 'Other'}
    </span>
  );
}
