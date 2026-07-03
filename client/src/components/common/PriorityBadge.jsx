const PRIORITY_STYLES = {
  High: 'bg-primary text-white border-primary',
  Medium: 'bg-primary/20 text-primary border-primary/30',
  Low: 'bg-secondary-100 text-gray-600 border-gray-200',
};

export default function PriorityBadge({ priority }) {
  const style = PRIORITY_STYLES[priority] || PRIORITY_STYLES.Low;
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${style}`}>
      {priority} Priority
    </span>
  );
}
