import { Menu, RefreshCw, Search, User, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useNewsContext } from '../../context/NewsContext';
import { formatDateTime } from '../../utils/format';
import ThemeToggle from './ThemeToggle';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/news', label: 'News' },
  { to: '/problems', label: 'Problems', badge: 'problems' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/departments', label: 'Departments', badge: 'departments' },
  { to: '/settings', label: 'Settings' },
];

function linkClass({ isActive }) {
  return [
    'relative inline-flex items-center whitespace-nowrap px-3.5 py-2 text-[15px] font-medium transition-colors duration-200',
    isActive
      ? 'text-primary after:absolute after:inset-x-3 after:-bottom-px after:h-0.5 after:rounded-full after:bg-primary'
      : 'text-muted hover:text-app',
  ].join(' ');
}

function NavBadge({ count }) {
  if (!count) return null;
  return (
    <span className="ml-1.5 inline-flex min-w-[1.15rem] items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-bold text-white">
      {count}
    </span>
  );
}

export default function TopNav() {
  const navigate = useNavigate();
  const { lastUpdated, refresh, refreshing, stats, departments } = useNewsContext();
  const [search, setSearch] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);

  const highCount = stats?.problemPriorityCounts?.High || 0;
  const deptsWithHigh = useMemo(
    () => (departments || []).filter((d) => d.high > 0).length,
    [departments]
  );

  const badges = {
    problems: highCount,
    departments: deptsWithHigh,
  };

  const submitSearch = (e) => {
    e?.preventDefault?.();
    const q = search.trim();
    navigate(q ? `/news?q=${encodeURIComponent(q)}` : '/news');
    setMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-40 border-b border-app/80 bg-navbar/95 backdrop-blur supports-[backdrop-filter]:bg-navbar/90 shadow-soft">
      <div className="mx-auto w-full max-w-none px-6">
        <div className="flex h-[4.25rem] items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-3 min-w-0 shrink-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-primary text-white font-bold text-sm tracking-wide shadow-soft">
              MS
            </div>
            <div className="min-w-0 hidden sm:block">
              <h1 className="truncate text-lg font-bold text-app tracking-tight leading-tight">
                MediaSphere
              </h1>
              <p className="truncate text-[12px] text-muted leading-snug mt-0.5">
                AI Powered Constituency Intelligence Platform
              </p>
            </div>
          </Link>

          <nav
            className="hidden lg:flex items-center gap-1 flex-1 justify-center"
            aria-label="Primary"
          >
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
                {item.label}
                {item.badge ? <NavBadge count={badges[item.badge]} /> : null}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2.5 shrink-0">
            <form onSubmit={submitSearch} className="relative hidden md:block w-44 xl:w-56">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
              <input
                type="search"
                placeholder="Search news..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input-field !py-2 !pl-9 !pr-3 !text-sm"
              />
            </form>

            <ThemeToggle />

            {typeof stats?.total === 'number' ? (
              <span
                className="hidden sm:inline-flex items-center rounded-control border border-app bg-surface px-2 py-1 text-xs font-semibold text-muted"
                title="Articles loaded from API"
              >
                {stats.total} news
              </span>
            ) : null}

            <button
              type="button"
              onClick={refresh}
              disabled={refreshing}
              title={lastUpdated ? `Updated ${formatDateTime(lastUpdated)}` : 'Refresh'}
              className="inline-flex h-9 w-9 items-center justify-center rounded-control border border-app bg-surface text-app hover:bg-app transition-colors duration-200 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>

            <Link
              to="/settings"
              title="Profile & settings"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-app bg-app text-muted hover:text-primary hover:border-primary/30 transition-colors duration-200"
            >
              <User className="h-4 w-4" />
            </Link>

            <button
              type="button"
              className="lg:hidden inline-flex h-9 w-9 items-center justify-center rounded-control border border-app bg-surface text-app"
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Toggle navigation"
            >
              {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className="md:hidden pb-3">
          <form onSubmit={submitSearch} className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
            <input
              type="search"
              placeholder="Search news..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field !py-2 !pl-9"
            />
          </form>
        </div>

        <div className={`lg:hidden pb-3 ${menuOpen ? 'block' : 'hidden sm:block'}`}>
          <nav className="flex gap-2 overflow-x-auto pb-1" aria-label="Primary mobile">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={linkClass}
                onClick={() => setMenuOpen(false)}
              >
                {item.label}
                {item.badge ? <NavBadge count={badges[item.badge]} /> : null}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>
    </header>
  );
}
