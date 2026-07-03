import {
  FiAlertTriangle,
  FiFileText,
  FiMinusCircle,
  FiThumbsDown,
  FiThumbsUp,
} from 'react-icons/fi';
import StatCard from './common/StatCard';

export default function SummaryCards({ stats }) {
  const { total, positive, negative, statements, problems, changeSinceYesterday } = stats;

  const cards = [
    {
      icon: FiFileText,
      label: 'Total News',
      count: total,
      change: changeSinceYesterday.total,
      highlight: true,
    },
    {
      icon: FiThumbsUp,
      label: 'Positive News',
      count: positive,
      change: changeSinceYesterday.positive,
    },
    {
      icon: FiThumbsDown,
      label: 'Negative News',
      count: negative,
      change: changeSinceYesterday.negative,
    },
    {
      icon: FiAlertTriangle,
      label: 'Problems Identified',
      count: problems,
      change: changeSinceYesterday.problems,
    },
    {
      icon: FiMinusCircle,
      label: 'Statements / General',
      count: statements,
      change: changeSinceYesterday.statements,
    },
  ];

  return (
    <section aria-label="Summary statistics">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {cards.map((card) => (
          <StatCard
            key={card.label}
            icon={card.icon}
            label={card.label}
            count={card.count}
            total={total}
            change={card.change}
            highlight={card.highlight}
          />
        ))}
      </div>
    </section>
  );
}
