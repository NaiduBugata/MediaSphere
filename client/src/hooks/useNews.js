import { useCallback, useEffect, useState } from 'react';
import { getNews } from '../services/api';
import { sortByDateDesc } from '../utils/format';

const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

export function useNews() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchNews = useCallback(async (options = {}) => {
    const { silent = false } = options;
    if (!silent) {
      setLoading(true);
    }
    setError(null);
    try {
      const data = await getNews();
      setArticles(sortByDateDesc(data));
      setLastUpdated(new Date());
    } catch (err) {
      setError(err?.message || 'Failed to load news data');
      if (!silent) {
        setArticles([]);
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchNews();

    const intervalId = setInterval(() => {
      fetchNews({ silent: true });
    }, REFRESH_INTERVAL_MS);

    const handleFocus = () => {
      fetchNews({ silent: true });
    };
    window.addEventListener('focus', handleFocus);

    return () => {
      clearInterval(intervalId);
      window.removeEventListener('focus', handleFocus);
    };
  }, [fetchNews]);

  return {
    articles,
    loading,
    error,
    lastUpdated,
    refresh: fetchNews,
  };
}
