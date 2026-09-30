import api from './api';
import { getAdminToken } from './adminApi';

function authHeader() {
  const token = getAdminToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Resolves to { contacts, today, automatic, hour, templates }. */
export async function listBirthdays() {
  const { data } = await api.get('/admin/birthdays', { headers: authHeader(), params: { _t: Date.now() } });
  return data;
}

export async function addBirthday(contact) {
  const { data } = await api.post('/admin/birthdays', contact, { headers: authHeader() });
  return data?.contact;
}

export async function sendBirthdayWish(id) {
  const { data } = await api.post(`/admin/birthdays/${encodeURIComponent(id)}/send`, {}, { headers: authHeader(), timeout: 60000 });
  return data?.contact;
}

export async function deleteBirthday(id) {
  await api.delete(`/admin/birthdays/${encodeURIComponent(id)}`, { headers: authHeader() });
}

export async function listMessageTemplates() {
  const { data } = await api.get('/admin/messages/templates', { headers: authHeader() });
  return data?.templates || [];
}

/** Resolves to [{ contactId, name, status: 'accepted' | 'failed', error }]. */
export async function sendMessages(payload) {
  const { data } = await api.post('/admin/messages', payload, { headers: authHeader(), timeout: 120000 });
  return data?.results || [];
}

export async function listSentMessages() {
  const { data } = await api.get('/admin/messages', { headers: authHeader(), params: { _t: Date.now() } });
  return data?.messages || [];
}

const FREE_TEXT_WINDOW_MS = 24 * 60 * 60 * 1000;

/** End of WhatsApp's 24-hour free-text window, or null when it is closed. */
export function freeTextUntil(lastInboundAt, now = Date.now()) {
  const at = lastInboundAt ? Date.parse(lastInboundAt) : NaN;
  if (!Number.isFinite(at) || now - at >= FREE_TEXT_WINDOW_MS) return null;
  return new Date(at + FREE_TEXT_WINDOW_MS);
}

export function fillTemplate(body, values) {
  return String(body || '').replace(/\{\{\s*(\w+)\s*\}\}/g, (whole, key) => (values[key] ? values[key] : whole));
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "09-30" and 1995 → "30 Sep 1995". */
export function formatBirthday(birthday, year) {
  const [month, day] = String(birthday || '').split('-').map(Number);
  if (!month || !day) return '—';
  return `${day} ${MONTHS[month - 1]}${year ? ` ${year}` : ''}`;
}

export function isBirthdayToday(birthday, today) {
  return Boolean(birthday) && String(today || '').slice(5) === birthday;
}
