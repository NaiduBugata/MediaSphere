import api from './api';
import { getAdminToken } from './adminApi';
import { newsApiBase } from '../../lib/apiBase';

export const VISIT_ACCEPT = '.pdf,.doc,.docx,.xls,.xlsx';
export const IMPORT_ACCEPT = '.xlsx,.docx,.pdf';
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

export async function uploadVisit({ title, place, visitDate, visitTime, detail, file }, onProgress) {
  const form = new FormData();
  form.append('title', title);
  if (place) form.append('place', place);
  if (visitDate) form.append('visitDate', visitDate);
  if (visitTime) form.append('visitTime', visitTime);
  if (detail) form.append('detail', detail);
  if (file) form.append('file', file);
  const { data } = await api.post('/admin/visits', form, multipartConfig(onProgress));
  return data?.visit;
}

/** One file listing many visits; resolves to { fileName, found, imported, duplicates, rejected }. */
export async function importVisits(file, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/admin/visits/import', form, multipartConfig(onProgress));
  return data;
}

function multipartConfig(onProgress) {
  return {
    // axios would JSON-encode FormData under the instance's JSON default; the browser fills in the boundary.
    headers: { ...authHeader(), 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: (event) => {
      if (onProgress && event.total) onProgress(Math.round((event.loaded / event.total) * 100));
    },
  };
}

export function templateUrl(format) {
  return `${newsApiBase()}/visits/template/${format}`;
}

export async function deleteVisit(id) {
  await api.delete(`/admin/visits/${encodeURIComponent(id)}`, { headers: authHeader() });
}

export function visitFileUrl(fileId, download = false) {
  const url = `${newsApiBase()}/visits/files/${encodeURIComponent(fileId)}`;
  return download ? `${url}?download=1` : url;
}

/** Stored as "HH:MM" or "HH:MM-HH:MM" (24-hour); shown as "10:30 AM" or "10:00 AM – 12:30 PM". */
export function formatVisitTime(value) {
  return String(value || '')
    .split('-')
    .map((part) => {
      const m = part.match(/^(\d{2}):(\d{2})$/);
      if (!m) return '';
      const hour = Number(m[1]);
      return `${hour % 12 || 12}:${m[2]} ${hour < 12 ? 'AM' : 'PM'}`;
    })
    .filter(Boolean)
    .join(' – ');
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
