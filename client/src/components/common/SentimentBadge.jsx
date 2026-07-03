import { SENTIMENT_COLORS } from '../../utils/format';

export default function SentimentBadge({ sentiment }) {
  const colors = SENTIMENT_COLORS[sentiment] || SENTIMENT_COLORS.Neutral;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${colors.bg} ${colors.text} ${colors.border}`}
    >
      {sentiment || 'Unknown'}
    </span>
  );
}
