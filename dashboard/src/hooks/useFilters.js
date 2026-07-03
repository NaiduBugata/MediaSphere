import { useCallback, useMemo, useState } from 'react';
import { getDateKey } from '../utils/format';

const DEFAULT_FILTERS = {
  search: '',
  category: '',
  subcategory: '',
  sentiment: '',
  district: '',
  mandal: '',
  village: '',
  dateFrom: '',
  dateTo: '',
};

function matchesSearch(article, search) {
  if (!search) return true;
  const q = search.toLowerCase();
  const fields = [
    article.title,
    article.summary,
    article.category,
    article.subcategory,
    article.location?.district,
    article.location?.mandal,
    article.location?.village,
    ...(article.keywords || []),
  ];
  return fields.some((f) => f && String(f).toLowerCase().includes(q));
}

function matchesDateRange(article, dateFrom, dateTo) {
  const key = getDateKey(article.created_on);
  if (!key) return !dateFrom && !dateTo;
  if (dateFrom && key < dateFrom) return false;
  if (dateTo && key > dateTo) return false;
  return true;
}

export function useFilters(articles) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  const setFilter = useCallback((key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  const filteredArticles = useMemo(() => {
    return articles.filter((article) => {
      if (filters.category && article.category !== filters.category) return false;
      if (filters.subcategory && article.subcategory !== filters.subcategory) return false;
      if (filters.sentiment && article.sentiment !== filters.sentiment) return false;
      if (filters.district && article.location?.district !== filters.district) return false;
      if (filters.mandal && article.location?.mandal !== filters.mandal) return false;
      if (filters.village && article.location?.village !== filters.village) return false;
      if (!matchesSearch(article, filters.search)) return false;
      if (!matchesDateRange(article, filters.dateFrom, filters.dateTo)) return false;
      return true;
    });
  }, [articles, filters]);

  return {
    filters,
    setFilter,
    resetFilters,
    filteredArticles,
  };
}
