import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  adminLogin,
  adminLogout,
  adminMe,
  clearAdminToken,
  getAdminFetchDetail,
  getAdminFetchHistory,
  getAdminFetchStatus,
  getAdminHealth,
  getAdminToken,
  retryAdminFetch,
  triggerAdminFetch,
} from '../services/adminApi';
import { formatDateTime, formatRelativeTime } from '../utils/format';

const HEADLINE_META = {
  healthy: { label: 'HEALTHY', className: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  running: { label: 'FETCH RUNNING', className: 'bg-sky-100 text-sky-800 border-sky-200' },
  failed: { label: 'FETCH FAILED', className: 'bg-red-100 text-red-800 border-red-200' },
  scheduler_delayed: {
    label: 'SCHEDULER DELAYED',
    className: 'bg-amber-100 text-amber-900 border-amber-200',
  },
  never_fetched: { label: 'NEVER FETCHED', className: 'bg-slate-100 text-slate-700 border-slate-200' },
  unknown: { label: 'UNKNOWN', className: 'bg-slate-100 text-slate-700 border-slate-200' },
};

function StatusPill({ status }) {
  const map = {
    success: 'bg-emerald-100 text-emerald-800',
    failed: 'bg-red-100 text-red-800',
    running: 'bg-sky-100 text-sky-800',
    skipped: 'bg-slate-100 text-slate-700',
    timeout: 'bg-amber-100 text-amber-900',
    cancelled: 'bg-slate-100 text-slate-600',
  };
  return (
    <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-semibold uppercase ${map[status] || map.skipped}`}>
      {status || '—'}
    </span>
  );
}

function StatCard({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-app bg-surface p-4 shadow-soft">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-xl font-bold text-app">{value ?? '—'}</p>
      {sub ? <p className="mt-1 text-xs text-muted">{sub}</p> : null}
    </div>
  );
}

function AdminLogin({ onSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await adminLogin(username, password);
      onSuccess();
    } catch (err) {
      const noResponse = !err?.response;
      const raw = err?.response?.data?.error || err?.message || '';
      const msg = noResponse
        ? 'API unreachable (often Render Free waking up). Wait ~60s and try again, or open https://mediasphere-1.onrender.com/api/health first.'
        : raw || 'Login failed. Check ADMIN_USERNAME / ADMIN_PASSWORD on the API.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-app flex items-center justify-center px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-md rounded-2xl border border-app bg-surface p-6 shadow-lift space-y-4"
      >
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">MediaSphere</p>
          <h1 className="text-2xl font-bold text-app mt-1">Admin sign-in</h1>
          <p className="text-sm text-muted mt-1">
            Protected ops console for pipeline fetch monitoring. Route: <code>/@admin</code>
          </p>
        </div>
        <label className="block text-sm">
          <span className="text-muted">Username / email</span>
          <input
            type="email"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="input-field mt-1 w-full"
            required
          />
        </label>
        <label className="block text-sm">
          <span className="text-muted">Password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input-field mt-1 w-full"
            required
          />
        </label>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-60"
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
        <Link to="/" className="block text-center text-sm text-muted hover:text-primary">
          ← Back to site
        </Link>
      </form>
    </div>
  );
}

function DetailModal({ run, onClose, onRetry }) {
  if (!run) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-app bg-surface p-5 shadow-lift"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-bold text-app">Fetch details</h3>
          <button type="button" onClick={onClose} className="text-muted hover:text-app text-sm">
            Close
          </button>
        </div>
        <dl className="mt-4 space-y-2 text-sm">
          {[
            ['Run ID', run.run_id],
            ['Trigger', run.trigger],
            ['Status', run.status],
            ['Started', formatDateTime(run.started_at)],
            ['Completed', formatDateTime(run.completed_at)],
            ['Duration', run.duration_seconds != null ? `${run.duration_seconds}s` : '—'],
            ['Fetched', run.records_fetched],
            ['Processed', run.records_processed],
            ['Inserted', run.records_inserted],
            ['Retry count', run.retry_count],
            ['Error', run.error_message || '—'],
          ].map(([k, v]) => (
            <div key={k} className="grid grid-cols-3 gap-2">
              <dt className="text-muted">{k}</dt>
              <dd className="col-span-2 text-app break-words">{v ?? '—'}</dd>
            </div>
          ))}
        </dl>
        {run.status === 'failed' ? (
          <button
            type="button"
            onClick={() => onRetry(run.run_id)}
            className="mt-4 w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
          >
            Retry fetch
          </button>
        ) : null}
      </div>
    </div>
  );
}

function AdminDashboard({ onLogout }) {
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [health, setHealth] = useState(null);
  const [filters, setFilters] = useState({ status: '', trigger: '', q: '' });
  const [busy, setBusy] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setError('');
      const [st, hist, hl] = await Promise.all([
        getAdminFetchStatus(),
        getAdminFetchHistory({
          limit: 40,
          status: filters.status || undefined,
          trigger: filters.trigger || undefined,
          q: filters.q || undefined,
        }),
        getAdminHealth(),
      ]);
      setStatus(st);
      setHistory(hist.runs || []);
      setHealth(hl);
    } catch (err) {
      if (err?.response?.status === 401) {
        clearAdminToken();
        window.location.reload();
        return;
      }
      setError(err?.response?.data?.error || err?.message || 'Failed to load admin data');
    }
  }, [filters.status, filters.trigger, filters.q]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const running = status?.headline === 'running';
    const ms = running ? 4000 : 15000;
    const id = setInterval(load, ms);
    return () => clearInterval(id);
  }, [load, status?.headline]);

  const headline = HEADLINE_META[status?.headline] || HEADLINE_META.unknown;

  const onFetchNow = async () => {
    setBusy(true);
    setActionMsg('Initializing…');
    try {
      const { data, status: http } = await triggerAdminFetch();
      if (http === 409 || data?.status === 'already_running') {
        setActionMsg(
          `A fetch operation is already running.${
            data?.lock?.acquired_at ? ` Started: ${formatDateTime(data.lock.acquired_at)}` : ''
          }`
        );
      } else if (data?.accepted) {
        setActionMsg(`Fetching… run ${data.run_id}`);
      } else {
        setActionMsg(data?.message || data?.error || 'Trigger failed');
      }
      await load();
    } catch (err) {
      setActionMsg(err?.message || 'Trigger failed');
    } finally {
      setBusy(false);
    }
  };

  const onRetry = async (runId) => {
    setBusy(true);
    setActionMsg(`Retry started for ${runId}`);
    try {
      const { data, status: http } = await retryAdminFetch(runId);
      if (http === 409) setActionMsg(data?.message || 'Already running');
      else setActionMsg(data?.accepted ? `Retry accepted (${data.run_id})` : data?.error || 'Retry failed');
      setDetail(null);
      await load();
    } catch (err) {
      setActionMsg(err?.message || 'Retry failed');
    } finally {
      setBusy(false);
    }
  };

  const openDetail = async (runId) => {
    try {
      const row = await getAdminFetchDetail(runId);
      setDetail(row);
    } catch (err) {
      setActionMsg(err?.message || 'Could not load run detail');
    }
  };

  const freshnessLabel = useMemo(() => {
    const f = status?.freshness;
    if (f === 'fresh') return '✓ Fresh';
    if (f === 'aging') return '• Aging';
    if (f === 'stale') return '⚠ Stale data';
    return '—';
  }, [status?.freshness]);

  return (
    <div className="min-h-screen bg-app text-app">
      <header className="border-b border-app bg-navbar/95 backdrop-blur sticky top-0 z-30">
        <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-primary">Admin</p>
            <h1 className="text-lg font-bold leading-tight">Fetch monitoring</h1>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/" className="text-sm text-muted hover:text-primary px-2">
              Site
            </Link>
            <button
              type="button"
              onClick={load}
              className="rounded-md border border-app bg-surface px-3 py-1.5 text-sm font-medium"
            >
              Refresh
            </button>
            <button
              type="button"
              onClick={async () => {
                await adminLogout();
                onLogout();
              }}
              className="rounded-md border border-app bg-surface px-3 py-1.5 text-sm font-medium"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 space-y-6">
        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        <section className="rounded-2xl border border-app bg-surface p-5 shadow-soft">
          <div className="flex flex-wrap items-center gap-3 justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">System status</p>
              <span className={`mt-2 inline-flex rounded-md border px-3 py-1 text-sm font-bold ${headline.className}`}>
                {headline.label}
              </span>
            </div>
            <div className="text-sm text-muted">
              Data freshness: <span className="font-semibold text-app">{freshnessLabel}</span>
              {status?.data_age_seconds != null ? (
                <span> · {formatRelativeTime(status.last_success)}</span>
              ) : null}
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Last successful" value={formatDateTime(status?.last_success)} />
            <StatCard label="Last attempt" value={formatDateTime(status?.last_run)} />
            <StatCard label="Next scheduled" value={formatDateTime(status?.next_run)} />
            <StatCard
              label="Last duration"
              value={
                status?.last_duration_seconds != null ? `${status.last_duration_seconds}s` : '—'
              }
              sub={`Inserted last run: ${status?.articles_inserted_last_run ?? '—'}`}
            />
          </div>
          <p className="mt-3 text-xs text-muted">
            Interval {status?.interval_hours ?? '—'}h · Tolerance {status?.delay_tolerance_minutes ?? '—'}m ·
            Articles in DB {status?.articles_count ?? '—'} · Scheduler {status?.scheduler ?? '—'}
          </p>
        </section>

        <section className="rounded-2xl border border-app bg-surface p-5 shadow-soft space-y-3">
          <button
            type="button"
            disabled={busy || status?.headline === 'running'}
            onClick={onFetchNow}
            className="w-full sm:w-auto rounded-xl bg-primary px-8 py-3 text-base font-bold text-white hover:bg-primary-hover disabled:opacity-60"
          >
            {status?.headline === 'running' || busy ? 'Fetching…' : 'FETCH DATA NOW'}
          </button>
          {actionMsg ? <p className="text-sm text-muted">{actionMsg}</p> : null}
        </section>

        {(status?.alerts || []).length > 0 ? (
          <section className="space-y-2">
            <h2 className="text-sm font-bold uppercase tracking-wide text-muted">Active alerts</h2>
            {status.alerts.map((a) => (
              <div
                key={a.code}
                className={`rounded-xl border px-4 py-3 text-sm ${
                  a.level === 'critical'
                    ? 'border-red-200 bg-red-50 text-red-900'
                    : a.level === 'warning'
                      ? 'border-amber-200 bg-amber-50 text-amber-950'
                      : 'border-sky-200 bg-sky-50 text-sky-950'
                }`}
              >
                <strong className="uppercase text-xs tracking-wide">{a.level}</strong>
                <p className="mt-0.5">{a.message}</p>
              </div>
            ))}
          </section>
        ) : null}

        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Successful runs" value={status?.stats?.successful} />
          <StatCard label="Failed runs" value={status?.stats?.failed} />
          <StatCard label="Skipped" value={status?.stats?.skipped} />
          <StatCard label="Running records" value={status?.stats?.running} />
        </section>

        {health?.checks ? (
          <section className="rounded-2xl border border-app bg-surface p-5 shadow-soft">
            <h2 className="text-sm font-bold uppercase tracking-wide text-muted mb-3">Health check</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
              {Object.entries(health.checks).map(([key, val]) => (
                <div key={key} className="rounded-lg border border-app px-3 py-2">
                  <p className="text-xs text-muted capitalize">{key.replace('_', ' ')}</p>
                  <p className={`font-semibold ${val.ok ? 'text-emerald-700' : 'text-red-700'}`}>
                    {val.ok ? '✓ OK' : '✕ Issue'}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section className="rounded-2xl border border-app bg-surface p-5 shadow-soft">
          <div className="flex flex-wrap items-end gap-3 justify-between mb-4">
            <h2 className="text-sm font-bold uppercase tracking-wide text-muted">Recent fetches</h2>
            <div className="flex flex-wrap gap-2">
              <select
                className="input-field !py-1.5 !text-sm"
                value={filters.status}
                onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
              >
                <option value="">All statuses</option>
                <option value="success">Success</option>
                <option value="failed">Failed</option>
                <option value="skipped">Skipped</option>
                <option value="running">Running</option>
              </select>
              <select
                className="input-field !py-1.5 !text-sm"
                value={filters.trigger}
                onChange={(e) => setFilters((f) => ({ ...f, trigger: e.target.value }))}
              >
                <option value="">All triggers</option>
                <option value="automatic">Automatic</option>
                <option value="manual">Manual</option>
                <option value="retry">Retry</option>
              </select>
              <input
                className="input-field !py-1.5 !text-sm"
                placeholder="Search errors…"
                value={filters.q}
                onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted border-b border-app">
                  <th className="py-2 pr-3">Date/Time</th>
                  <th className="py-2 pr-3">Trigger</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Duration</th>
                  <th className="py-2 pr-3">Items</th>
                  <th className="py-2 pr-3">Error</th>
                  <th className="py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-6 text-muted">
                      No fetch history yet.
                    </td>
                  </tr>
                ) : (
                  history.map((run) => (
                    <tr key={run.run_id || run.id} className="border-b border-app/60">
                      <td className="py-2.5 pr-3 whitespace-nowrap">{formatDateTime(run.started_at)}</td>
                      <td className="py-2.5 pr-3 capitalize">{run.trigger}</td>
                      <td className="py-2.5 pr-3">
                        <StatusPill status={run.status} />
                      </td>
                      <td className="py-2.5 pr-3">
                        {run.duration_seconds != null ? `${run.duration_seconds}s` : '—'}
                      </td>
                      <td className="py-2.5 pr-3">{run.records_inserted ?? 0}</td>
                      <td className="py-2.5 pr-3 max-w-[220px] truncate text-muted">
                        {run.error_message || '—'}
                      </td>
                      <td className="py-2.5 whitespace-nowrap space-x-2">
                        <button
                          type="button"
                          className="text-primary font-medium hover:underline"
                          onClick={() => openDetail(run.run_id)}
                        >
                          View
                        </button>
                        {run.status === 'failed' ? (
                          <button
                            type="button"
                            className="text-primary font-medium hover:underline"
                            onClick={() => onRetry(run.run_id)}
                            disabled={busy}
                          >
                            Retry
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <DetailModal run={detail} onClose={() => setDetail(null)} onRetry={onRetry} />
    </div>
  );
}

export default function AdminPage() {
  const [authed, setAuthed] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!getAdminToken()) {
        if (!cancelled) {
          setAuthed(false);
          setChecking(false);
        }
        return;
      }
      try {
        await adminMe();
        if (!cancelled) setAuthed(true);
      } catch {
        clearAdminToken();
        if (!cancelled) setAuthed(false);
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-app text-muted text-sm">
        Checking admin session…
      </div>
    );
  }

  if (!authed) {
    return <AdminLogin onSuccess={() => setAuthed(true)} />;
  }

  return <AdminDashboard onLogout={() => setAuthed(false)} />;
}
