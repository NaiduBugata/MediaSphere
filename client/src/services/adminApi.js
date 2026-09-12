import api from './api';

const ADMIN_TOKEN_KEY = 'mediasphere.admin.token';

export function getAdminToken() {
  try {
    return localStorage.getItem(ADMIN_TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setAdminToken(token) {
  try {
    if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token);
    else localStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export function clearAdminToken() {
  setAdminToken('');
}

function adminHeaders() {
  const token = getAdminToken();
  return token
    ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };
}

export async function adminLogin(username, password) {
  const { data } = await api.post('/admin/auth/login', { username, password });
  if (data?.token) setAdminToken(data.token);
  return data;
}

export async function adminLogout() {
  try {
    await api.post('/admin/auth/logout', {}, { headers: adminHeaders() });
  } catch {
    /* ignore */
  }
  clearAdminToken();
}

export async function adminMe() {
  const { data } = await api.get('/admin/auth/me', { headers: adminHeaders() });
  return data;
}

export async function getAdminFetchStatus() {
  const { data } = await api.get('/admin/fetch/status', {
    headers: adminHeaders(),
    params: { _t: Date.now() },
  });
  return data;
}

export async function triggerAdminFetch() {
  const { data, status } = await api.post(
    '/admin/fetch/trigger',
    {},
    { headers: adminHeaders(), validateStatus: () => true }
  );
  return { data, status };
}

export async function retryAdminFetch(runId) {
  const { data, status } = await api.post(
    `/admin/fetch/retry/${encodeURIComponent(runId)}`,
    {},
    { headers: adminHeaders(), validateStatus: () => true }
  );
  return { data, status };
}

export async function getAdminFetchHistory(params = {}) {
  const { data } = await api.get('/admin/fetch/history', {
    headers: adminHeaders(),
    params: { ...params, _t: Date.now() },
  });
  return data;
}

export async function getAdminFetchDetail(runId) {
  const { data } = await api.get(`/admin/fetch/${encodeURIComponent(runId)}`, {
    headers: adminHeaders(),
  });
  return data;
}

export async function getAdminHealth() {
  const { data } = await api.get('/admin/health', {
    headers: adminHeaders(),
    params: { _t: Date.now() },
  });
  return data;
}
