import { SENTIMENT_COLORS } from '../../utils/format';

export default function SentimentBadge({ sentiment }) {
  const colors = SENTIMENT_COLORS[sentiment] || SENTIMENT_COLORS.Neutral;
  return (
    <span className={`badge-pill border ${colors.bg} ${colors.text} ${colors.border}`}>
      {sentiment || 'Unknown'}
    </span>
  );
}
