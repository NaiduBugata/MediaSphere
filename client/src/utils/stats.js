import { getDateKey, parseDate, uniqueSorted } from './format';
import { enrichArticles, isProblem, sortByPriority } from './derive';

function countBy(items, getter) {
  const map = {};
  for (const item of items) {
    const key = getter(item) || 'Unknown';
    map[key] = (map[key] || 0) + 1;
  }
  return map;
}

function topEntry(counts, excludeUnknown = true) {
  const entries = Object.entries(counts)
    .filter(([k]) => !excludeUnknown || (k !== 'Unknown' && k !== '—' && k !== null))
    .sort((a, b) => b[1] - a[1]);
  return entries[0] || ['—', 0];
}

function countOnDate(articles, dateKey) {
  return articles.filter((a) => getDateKey(a.created_on) === dateKey).length;
}

function buildDailyTrend(articles, days = 7) {
  const result = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    result.push({
      date: key,
      label: d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }),
      count: countOnDate(articles, key),
    });
  }
  return result;
}

function countKeywords(articles) {
  const map = {};
  for (const a of articles) {
    for (const kw of a.keywords || []) {
      if (kw) map[kw] = (map[kw] || 0) + 1;
    }
  }
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([name, count]) => ({ name, count }));
}

function countEntities(articles) {
  const map = {};
  for (const a of articles) {
    for (const e of a.entities || []) {
      const name = typeof e === 'object' ? e.name : String(e);
      if (name) map[name] = (map[name] || 0) + 1;
    }
  }
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([name, count]) => ({ name, count }));
}

export function computeStats(articles) {
  const enriched = enrichArticles(articles);
  const total = enriched.length;

  const positive = enriched.filter((a) => a.sentiment === 'Positive');
  const negative = enriched.filter((a) => a.sentiment === 'Negative');
  const neutral = enriched.filter((a) => a.sentiment === 'Neutral');
  const statements = enriched.filter((a) => a.sentiment === 'Statement');
  const problems = enriched.filter(isProblem);
  const highPriority = problems.filter((a) => a.priority === 'High');

  const problemPriorityCounts = { High: 0, Medium: 0, Low: 0 };
  for (const p of problems) {
    if (p.priority in problemPriorityCounts) {
      problemPriorityCounts[p.priority] += 1;
    }
  }

  const todayKey = new Date().toISOString().slice(0, 10);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayKey = yesterday.toISOString().slice(0, 10);

  const sentimentCounts = countBy(enriched, (a) => a.sentiment || 'Unknown');
  const categoryCounts = countBy(enriched, (a) => a.category || 'Other');
  const districtCounts = countBy(enriched, (a) => a.location?.district);
  const mandalCounts = countBy(enriched, (a) => a.location?.mandal);
  const villageCounts = countBy(enriched, (a) => a.location?.village);

  const problemMandalCounts = countBy(problems, (a) => a.location?.mandal);
  const problemVillageCounts = countBy(problems, (a) => a.location?.village);

  const [topMandal] = topEntry(problemMandalCounts);
  const [topVillage] = topEntry(problemVillageCounts);
  const [topCategory] = topEntry(categoryCounts);

  const dates = enriched
    .map((a) => parseDate(a.created_on))
    .filter(Boolean)
    .sort((a, b) => a - b);

  const filterOptions = {
    categories: uniqueSorted(enriched.map((a) => a.category)),
    subcategories: uniqueSorted(enriched.map((a) => a.subcategory)),
    sentiments: uniqueSorted(enriched.map((a) => a.sentiment)),
    districts: uniqueSorted(enriched.map((a) => a.location?.district)),
    mandals: uniqueSorted(enriched.map((a) => a.location?.mandal)),
    villages: uniqueSorted(enriched.map((a) => a.location?.village)),
  };

  return {
    total,
    positive: positive.length,
    negative: negative.length,
    neutral: neutral.length,
    statements: statements.length,
    problems: problems.length,
    highPriorityProblems: highPriority.length,
    problemPriorityCounts,
    sentimentCounts,
    categoryCounts,
    districtCounts,
    mandalCounts,
    villageCounts,
    dailyTrend: buildDailyTrend(enriched),
    topKeywords: countKeywords(enriched),
    topEntities: countEntities(enriched),
    topMandal,
    topVillage,
    topCategory,
    districtsCovered: Object.keys(districtCounts).filter((k) => k && k !== 'Unknown').length,
    mandalsCovered: Object.keys(mandalCounts).filter((k) => k && k !== 'Unknown').length,
    villagesCovered: Object.keys(villageCounts).filter((k) => k && k !== 'Unknown').length,
    latestTime: dates.length ? dates[dates.length - 1].toISOString() : null,
    oldestTime: dates.length ? dates[0].toISOString() : null,
    changeSinceYesterday: {
      total: countOnDate(enriched, todayKey) - countOnDate(enriched, yesterdayKey),
      positive:
        countOnDate(positive, todayKey) - countOnDate(positive, yesterdayKey),
      negative:
        countOnDate(negative, todayKey) - countOnDate(negative, yesterdayKey),
      problems:
        countOnDate(problems, todayKey) - countOnDate(problems, yesterdayKey),
      statements:
        countOnDate(statements, todayKey) - countOnDate(statements, yesterdayKey),
    },
    actionRequired: sortByPriority(problems).slice(0, 10),
    positiveDevelopments: positive.slice(0, 8),
    recentActivity: enriched.slice(0, 5),
    filterOptions,
    enriched,
  };
}

export function toChartData(counts, limit = 10) {
  return Object.entries(counts || {})
    .filter(([name]) => name && name !== 'Unknown')
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, value]) => ({ name, value }));
}

export function toSentimentChartData(sentimentCounts) {
  const order = ['Positive', 'Negative', 'Neutral', 'Statement'];
  return order
    .filter((s) => sentimentCounts[s])
    .map((name) => ({ name, value: sentimentCounts[name] }));
}
