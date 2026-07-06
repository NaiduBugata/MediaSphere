export function safeString(value, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

export function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

export function parseDate(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(value) {
  const d = parseDate(value);
  if (!d || Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function formatDateTime(value) {
  const d = parseDate(value);
  if (!d) return '—';
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  });
}

export function formatRelativeTime(value) {
  const d = parseDate(value);
  if (!d || Number.isNaN(d.getTime())) return '—';
  const diffMs = Date.now() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(value);
}

export function formatPercent(count, total) {
  if (!total) return '0%';
  return `${Math.round((count / total) * 100)}%`;
}

export function formatLocation(location) {
  if (!location || typeof location !== 'object') return '—';
  const parts = [location.village, location.town, location.mandal, location.district].filter(Boolean);
  return parts.length ? parts.join(', ') : '—';
}

export function getDateKey(value) {
  const d = parseDate(value);
  if (!d || Number.isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}

export function isToday(value) {
  const key = getDateKey(value);
  if (!key) return false;
  return key === new Date().toISOString().slice(0, 10);
}

export function isYesterday(value) {
  const key = getDateKey(value);
  if (!key) return false;
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  return key === yesterday.toISOString().slice(0, 10);
}

export const SENTIMENT_COLORS = {
  Positive: { bg: 'bg-primary-50', text: 'text-primary-800', border: 'border-primary-200' },
  Negative: { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-300' },
  Neutral: { bg: 'bg-secondary-100', text: 'text-gray-600', border: 'border-gray-200' },
  Statement: { bg: 'bg-secondary', text: 'text-gray-700', border: 'border-gray-200' },
};

export const CATEGORY_COLORS = {
  Employment: 'bg-primary-100 text-primary-800',
  Transport: 'bg-primary-50 text-primary-700',
  Agriculture: 'bg-primary-100 text-primary-900',
  Health: 'bg-primary-50 text-primary-800',
  Education: 'bg-primary-100 text-primary-800',
  Roads: 'bg-primary-50 text-primary-700',
  Infrastructure: 'bg-primary-100 text-primary-900',
  Politics: 'bg-gray-100 text-gray-800',
  Water: 'bg-primary-50 text-primary-800',
  Crime: 'bg-gray-200 text-gray-900',
  'Social Welfare': 'bg-primary-50 text-primary-700',
  Other: 'bg-secondary-100 text-gray-700',
};

export function getCategoryColor(category) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS.Other;
}

export function truncate(text, max = 120) {
  if (!text) return '';
  if (text.length <= max) return text;
  return `${text.slice(0, max).trim()}…`;
}

/** Best timestamp for ordering (newest first across Lokal + YouTube). */
export function getArticleSortTime(article) {
  for (const field of ['created_on', 'first_seen_at', 'last_updated_at']) {
    const t = parseDate(article?.[field])?.getTime();
    if (t) return t;
  }
  return 0;
}

export function isYoutubeSource(source) {
  return (source || '').toLowerCase() === 'youtube';
}

export function formatSourceLabel(source) {
  return isYoutubeSource(source) ? 'YT' : 'Lokal Telugu';
}

export function sortByDateDesc(articles) {
  return [...articles].sort((a, b) => {
    const da = getArticleSortTime(a);
    const db = getArticleSortTime(b);
    if (db !== da) return db - da;
    const sa = formatSourceLabel(a.source);
    const sb = formatSourceLabel(b.source);
    return sa.localeCompare(sb);
  });
}

export function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b))
  );
}
