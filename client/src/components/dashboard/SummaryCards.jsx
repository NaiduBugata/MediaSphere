import {
  FileText,
  MinusCircle,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
} from 'lucide-react';
import StatCard from '../common/StatCard';

export default function SummaryCards({ stats, compact = false }) {
  const { total, positive, negative, statements, problems, changeSinceYesterday } = stats;

  const cards = [
    {
      icon: FileText,
      label: 'Total News',
      count: total,
      change: changeSinceYesterday.total,
      highlight: true,
    },
    {
      icon: ThumbsUp,
      label: 'Positive',
      count: positive,
      change: changeSinceYesterday.positive,
    },
    {
      icon: ThumbsDown,
      label: 'Negative',
      count: negative,
      change: changeSinceYesterday.negative,
    },
    {
      icon: TriangleAlert,
      label: 'Problems',
      count: problems,
      change: changeSinceYesterday.problems,
    },
    {
      icon: MinusCircle,
      label: 'Statements',
      count: statements,
      change: changeSinceYesterday.statements,
    },
  ];

  return (
    <section aria-label="Quick stats" className="shrink-0">
      {!compact && <h2 className="section-title mb-4">Quick Stats</h2>}
      <div
        className={`grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 items-stretch ${
          compact ? 'gap-2' : 'gap-4'
        }`}
      >
        {cards.map((card) => (
          <StatCard
            key={card.label}
            icon={card.icon}
            label={card.label}
            count={card.count}
            total={total}
            change={card.change}
            highlight={card.highlight}
            compact={compact}
          />
        ))}
      </div>
    </section>
  );
}
