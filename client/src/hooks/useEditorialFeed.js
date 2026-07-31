import { useMemo } from 'react';
import { pickFeaturedArticle, scoreHeroImage } from '../utils/articleMedia';

/**
 * Split articles into featured hero, right-rail list, and latest row.
 * Featured prefers a strong landscape image; falls back through candidates.
 */
export function useEditorialFeed(articles, stats) {
  return useMemo(() => {
    const list = articles || [];
    const action = stats?.actionRequired || list.filter((a) => a.isActionRequired);

    // Prefer recent pool; bias toward action items when image scores are close.
    const pool = [];
    const seen = new Set();
    for (const a of [...action, ...list.slice(0, 48)]) {
      const id = a?._id || a?.post_id;
      if (!a || id == null || seen.has(id)) continue;
      seen.add(id);
      pool.push(a);
    }

    const featured =
      pickFeaturedArticle(pool) ||
      action.find((a) => scoreHeroImage(a) > 0) ||
      action[0] ||
      list[0] ||
      null;

    const featuredId = featured?._id || featured?.post_id;

    const rail = (action.length ? action : list)
      .filter((a) => (a._id || a.post_id) !== featuredId)
      .slice(0, 5);

    const railIds = new Set(rail.map((a) => a._id || a.post_id));
    if (featuredId) railIds.add(featuredId);

    const latest = list.filter((a) => !railIds.has(a._id || a.post_id)).slice(0, 4);

    const trending =
      stats?.topKeywords?.length > 0
        ? stats.topKeywords
        : list.slice(0, 6).map((a) => a.title);

    return { featured, rail, latest, trending };
  }, [articles, stats]);
}
