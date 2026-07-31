import { getCategoryColor, formatCategoryLabel } from '../../utils/format';

export default function CategoryChip({ category }) {
  const colorClass = getCategoryColor(category);
  return (
    <span className={`badge-pill ${colorClass}`}>
      {formatCategoryLabel(category) || 'Other'}
    </span>
  );
}
