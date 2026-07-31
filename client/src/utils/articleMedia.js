/**
 * Resolve a display image for an article.
 * Priority: explicit image fields → thumbnail → nested media → YouTube URL → null.
 */

function extractYoutubeId(url) {
  if (!url || typeof url !== 'string') return null;
  try {
    const u = new URL(url);
    if (u.hostname.includes('youtu.be')) {
      return u.pathname.replace(/^\//, '').split('/')[0] || null;
    }
    if (u.hostname.includes('youtube.com')) {
      const v = u.searchParams.get('v');
      if (v) return v;
      const parts = u.pathname.split('/').filter(Boolean);
      const embedIdx = parts.indexOf('embed');
      if (embedIdx >= 0 && parts[embedIdx + 1]) return parts[embedIdx + 1];
      const shortIdx = parts.indexOf('shorts');
      if (shortIdx >= 0 && parts[shortIdx + 1]) return parts[shortIdx + 1];
    }
  } catch {
    // fall through
  }
  const m = String(url).match(
    /(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([A-Za-z0-9_-]{6,})/
  );
  return m?.[1] || null;
}

function firstHttpUrl(...candidates) {
  for (const value of candidates) {
    if (typeof value === 'string') {
      const url = value.trim();
      if (url.startsWith('http://') || url.startsWith('https://')) return url;
    }
  }
  return null;
}

function youtubeThumb(id, quality = 'hqdefault') {
  return `https://i.ytimg.com/vi/${id}/${quality}.jpg`;
}

export function getArticleImage(article, options = {}) {
  if (!article) return null;
  const { preferHero = false } = options;

  const direct = firstHttpUrl(
    article.image_url,
    article.image,
    article.featured_image,
    article.cover_image,
    article.banner,
    article.thumbnail,
    article.thumbnail_url
  );
  if (direct) return direct;

  const nested = article.media;
  if (nested && typeof nested === 'object') {
    const fromMedia = firstHttpUrl(
      nested.image,
      nested.image_url,
      nested.url,
      nested.thumbnail,
      nested.thumb_url
    );
    if (fromMedia) return fromMedia;
  }

  const source = (article.source || '').toLowerCase();
  if (source === 'youtube' || (article.source_url || '').includes('youtu')) {
    const id = extractYoutubeId(article.source_url);
    if (id) {
      return youtubeThumb(id, preferHero ? 'maxresdefault' : 'hqdefault');
    }
  }

  return null;
}

/**
 * Heuristic score for hero suitability (landscape / strong visual).
 * Higher is better; 0 means unsuitable (no usable image).
 */
export function scoreHeroImage(article) {
  const url = getArticleImage(article);
  if (!url) return 0;

  const lower = url.toLowerCase();
  if (/\/icon|avatar|logo|sprite|1x1|pixel|favicon/.test(lower)) return 0;

  let score = 10;

  if (lower.includes('ytimg.com') || lower.includes('youtube')) {
    if (lower.includes('maxresdefault') || lower.includes('hq720')) score += 55;
    else if (lower.includes('sddefault')) score += 40;
    else if (lower.includes('hqdefault') || lower.includes('mqdefault')) score += 32;
    else score += 24;
  } else if (lower.includes('getlokalapp.com') || lower.includes('media.getlokal')) {
    score += lower.includes('/cache/') ? 28 : 48;
  } else if (lower.includes('sakshi') || lower.includes('eenadu') || lower.includes('andhrajyothy')) {
    score += 36;
  } else {
    score += 18;
  }

  if (/wide|banner|cover|featured|hero|landscape|16[_-]?9|1920|1280|1200/.test(lower)) {
    score += 12;
  }
  if (/portrait|square|_sm\.|small|thumb_sm/.test(lower)) {
    score -= 14;
  }

  if (article.summary && String(article.summary).trim().length > 40) score += 6;
  if (article.isActionRequired) score += 4;

  return Math.max(0, score);
}

/** Pick the visually strongest featured candidate (landscape preferred). */
export function pickFeaturedArticle(candidates = []) {
  const list = (candidates || []).filter(Boolean);
  if (!list.length) return null;

  let best = null;
  let bestScore = -1;

  for (const article of list) {
    const score = scoreHeroImage(article);
    if (score > bestScore) {
      bestScore = score;
      best = article;
    }
  }

  if (bestScore > 0) return best;
  return list.find((a) => getArticleImage(a)) || list[0];
}

/** @deprecated Prefer getArticleImage — kept for existing imports. */
export function getArticleImageUrl(article) {
  return getArticleImage(article);
}

export function getPlaceholderLabel(article) {
  const cat = (article?.category || 'N').trim();
  return cat.charAt(0).toUpperCase();
}
