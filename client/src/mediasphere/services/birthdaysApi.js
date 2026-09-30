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
