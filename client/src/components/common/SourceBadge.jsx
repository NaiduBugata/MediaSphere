import { formatSourceLabel, isSakshiSource, isYoutubeSource } from '../../utils/format';

const STYLES = {
  lokal: 'bg-emerald-100 text-emerald-800',
  youtube: 'bg-red-100 text-red-800',
  sakshi: 'bg-amber-100 text-amber-900',
};

export default function SourceBadge({ source }) {
  let key = 'lokal';
  if (isYoutubeSource(source)) key = 'youtube';
  else if (isSakshiSource(source)) key = 'sakshi';
  const label = formatSourceLabel(source);
  const style = STYLES[key] || STYLES.lokal;

  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {label}
    </span>
  );
}
