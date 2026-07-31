const PRIORITY_STYLES = {
  High: 'bg-primary text-white border-primary',
  Medium: 'bg-primary/15 text-primary border-primary/25',
  Low: 'bg-app text-muted border-app',
};

export default function PriorityBadge({ priority }) {
  const style = PRIORITY_STYLES[priority] || PRIORITY_STYLES.Low;
  return (
    <span className={`badge-pill border ${style}`}>{priority} Priority</span>
  );
}
