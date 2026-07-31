import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

export async function getNews() {
  const { data } = await api.get('/news');
  return {
    articles: data.articles || [],
    count: data.count || 0,
    dataRevision: data.data_revision || null,
  };
}

export async function getStats() {
  const { data } = await api.get('/news/stats');
  return data;
}

export default api;
