/** Department helpers for Departments page and deep links. */

export function departmentToSlug(name) {
  return String(name || 'general-administration')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

export function slugToDepartment(slug, departments) {
  if (!slug) return null;
  const match = (departments || []).find((d) => departmentToSlug(d.name) === slug);
  return match?.name || null;
}

/**
 * Aggregate enriched articles by derived department.
 * @param {Array} articles - enriched articles with department, priority, isActionRequired
 */
export function computeDepartmentStats(articles) {
  const map = new Map();

  for (const article of articles || []) {
    const name = article.department || 'General Administration';
    if (!map.has(name)) {
      map.set(name, {
        name,
        slug: departmentToSlug(name),
        total: 0,
        problems: 0,
        high: 0,
        medium: 0,
        low: 0,
        latest: null,
        items: [],
      });
    }
    const row = map.get(name);
    row.total += 1;
    row.items.push(article);
    if (article.isActionRequired) {
      row.problems += 1;
      if (article.priority === 'High') row.high += 1;
      else if (article.priority === 'Medium') row.medium += 1;
      else row.low += 1;
    }
  }

  const list = Array.from(map.values()).map((row) => {
    const sorted = [...row.items].sort((a, b) => {
      const ta = new Date(a.created_on || a.first_seen_at || 0).getTime();
      const tb = new Date(b.created_on || b.first_seen_at || 0).getTime();
      return tb - ta;
    });
    return {
      ...row,
      items: sorted,
      problemsList: sorted.filter((a) => a.isActionRequired),
      latest: sorted[0] || null,
    };
  });

  list.sort((a, b) => b.high - a.high || b.problems - a.problems || b.total - a.total);
  return list;
}
