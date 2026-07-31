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
  Positive: { bg: 'bg-success/15', text: 'text-success', border: 'border-success/30' },
  Negative: { bg: 'bg-danger/15', text: 'text-danger', border: 'border-danger/30' },
  Neutral: { bg: 'bg-app', text: 'text-muted', border: 'border-app' },
  Statement: { bg: 'bg-primary/10', text: 'text-primary', border: 'border-primary/20' },
};

export const CATEGORY_COLORS = {
  Employment: 'bg-primary/10 text-primary',
  Transport: 'bg-primary/10 text-primary',
  Agriculture: 'bg-success/15 text-success',
  Health: 'bg-danger/10 text-danger',
  Education: 'bg-warning/15 text-warning',
  Roads: 'bg-primary/10 text-primary',
  Infrastructure: 'bg-primary/10 text-primary',
  Politics: 'bg-app text-muted',
  Water: 'bg-primary/10 text-primary',
  'Water Supply': 'bg-primary/10 text-primary',
  Crime: 'bg-danger/15 text-danger',
  'Social Welfare': 'bg-primary/10 text-primary',
  'Women & Child Welfare': 'bg-primary/10 text-primary',
  Electricity: 'bg-warning/15 text-warning',
  Drainage: 'bg-primary/10 text-primary',
  Environment: 'bg-success/15 text-success',
  'Government Schemes': 'bg-primary/10 text-primary',
  Youth: 'bg-primary/10 text-primary',
  Other: 'bg-app text-muted',
};

/** Constituency-focused display labels for issue categories (filter values unchanged). */
const CATEGORY_LABELS = {
  Roads: 'Roads',
  Water: 'Water Supply',
  'Water Supply': 'Water Supply',
  Agriculture: 'Agriculture',
  Health: 'Health',
  Education: 'Education',
  Transport: 'Transport',
  Crime: 'Crime',
  'Government Schemes': 'Government Schemes',
  Employment: 'Employment',
  Electricity: 'Electricity',
  Drainage: 'Drainage',
  Environment: 'Environment',
  Politics: 'Politics',
  'Social Welfare': 'Women & Child Welfare',
  'Women & Child Welfare': 'Women & Child Welfare',
  Youth: 'Youth',
  Infrastructure: 'Infrastructure',
  Other: 'Other',
};

export function formatCategoryLabel(category) {
  if (!category) return 'Other';
  return CATEGORY_LABELS[category] || category;
}

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

export function isSakshiSource(source) {
  return (source || '').toLowerCase() === 'sakshi';
}

export function formatSourceLabel(source) {
  const key = (source || '').toLowerCase();
  if (key === 'youtube') return 'YT';
  if (key === 'sakshi') return 'Sakshi';
  return 'Lokal Telugu';
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
