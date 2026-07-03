import { useCallback, useEffect, useState } from 'react';
import { getNews } from '../services/api';
import { sortByDateDesc } from '../utils/format';

export function useNews() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchNews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getNews();
      setArticles(sortByDateDesc(data));
      setLastUpdated(new Date());
    } catch (err) {
      setError(err?.message || 'Failed to load news data');
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNews();
  }, [fetchNews]);

  return {
    articles,
    loading,
    error,
    lastUpdated,
    refresh: fetchNews,
  };
}
