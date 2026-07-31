import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useNews } from '../hooks/useNews';
import { enrichArticles } from '../utils/derive';
import { computeStats } from '../utils/stats';
import { computeDepartmentStats } from '../utils/departments';

const NewsContext = createContext(null);

export function NewsProvider({ children }) {
  const { articles, loading, error, lastUpdated, dataRevision, refresh } = useNews();
  const enriched = useMemo(() => enrichArticles(articles), [articles]);
  const stats = useMemo(() => computeStats(enriched), [enriched]);
  const departments = useMemo(() => computeDepartmentStats(enriched), [enriched]);

  const [selectedArticle, setSelectedArticle] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const openArticle = useCallback((article) => {
    setSelectedArticle(article);
    setModalOpen(true);
  }, []);

  const closeArticle = useCallback(() => {
    setModalOpen(false);
    setSelectedArticle(null);
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  }, [refresh]);

  const value = useMemo(
    () => ({
      articles: enriched,
      rawArticles: articles,
      loading,
      error,
      lastUpdated,
      dataRevision,
      stats,
      departments,
      selectedArticle,
      modalOpen,
      refreshing,
      openArticle,
      closeArticle,
      refresh: handleRefresh,
    }),
    [
      enriched,
      articles,
      loading,
      error,
      lastUpdated,
      dataRevision,
      stats,
      departments,
      selectedArticle,
      modalOpen,
      refreshing,
      openArticle,
      closeArticle,
      handleRefresh,
    ]
  );

  return <NewsContext.Provider value={value}>{children}</NewsContext.Provider>;
}

export function useNewsContext() {
  const ctx = useContext(NewsContext);
  if (!ctx) {
    throw new Error('useNewsContext must be used within NewsProvider');
  }
  return ctx;
}
