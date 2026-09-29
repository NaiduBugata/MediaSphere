import api from './api';
import { getAdminToken } from './adminApi';
import { newsApiBase } from '../../lib/apiBase';

export const VISIT_ACCEPT = '.pdf,.doc,.docx,.xls,.xlsx';
export const VISIT_MAX_MB = 10;

export const VISIT_KIND_LABEL = { pdf: 'PDF', word: 'Word', excel: 'Excel' };

function authHeader() {
  const token = getAdminToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function listVisits() {
  const { data } = await api.get('/visits', { params: { _t: Date.now() } });
  return data?.visits || [];
}

export async function uploadVisit({ title, place, visitDate, detail, file }, onProgress) {
  const form = new FormData();
  form.append('title', title);
  if (place) form.append('place', place);
  if (visitDate) form.append('visitDate', visitDate);
  if (detail) form.append('detail', detail);
  form.append('file', file);
  const { data } = await api.post('/admin/visits', form, {
    // axios would JSON-encode FormData under the instance's JSON default; the browser fills in the boundary.
    headers: { ...authHeader(), 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: (event) => {
      if (onProgress && event.total) onProgress(Math.round((event.loaded / event.total) * 100));
    },
  });
  return data?.visit;
}

export async function deleteVisit(id) {
  await api.delete(`/admin/visits/${encodeURIComponent(id)}`, { headers: authHeader() });
}

export function visitFileUrl(fileId, download = false) {
  const url = `${newsApiBase()}/visits/files/${encodeURIComponent(fileId)}`;
  return download ? `${url}?download=1` : url;
}

export function formatFileSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function apiErrorMessage(err, fallback) {
  const message = err?.response?.data?.message;
  if (Array.isArray(message)) return message.join(', ');
  if (typeof message === 'string' && message) return message;
  if (err?.response?.status === 401) return 'Session expired. Please sign in again.';
  if (err?.response?.status === 413) return `File is too large (max ${VISIT_MAX_MB} MB).`;
  return err?.message || fallback;
}
