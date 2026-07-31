import { formatSourceLabel, isSakshiSource, isYoutubeSource } from '../../utils/format';

const STYLES = {
  lokal: 'bg-success/15 text-success',
  youtube: 'bg-primary/15 text-primary',
  sakshi: 'bg-warning/15 text-warning',
};

export default function SourceBadge({ source }) {
  let key = 'lokal';
  if (isYoutubeSource(source)) key = 'youtube';
  else if (isSakshiSource(source)) key = 'sakshi';
  const label = formatSourceLabel(source);
  const style = STYLES[key] || STYLES.lokal;

  return <span className={`badge-pill ${style}`}>{label}</span>;
}
