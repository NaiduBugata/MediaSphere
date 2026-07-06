import { formatSourceLabel, isYoutubeSource } from '../../utils/format';

const STYLES = {
  lokal: 'bg-emerald-100 text-emerald-800',
  youtube: 'bg-red-100 text-red-800',
};

export default function SourceBadge({ source }) {
  const key = isYoutubeSource(source) ? 'youtube' : 'lokal';
  const label = formatSourceLabel(source);
  const style = STYLES[key] || STYLES.lokal;

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {label}
    </span>
  );
}
