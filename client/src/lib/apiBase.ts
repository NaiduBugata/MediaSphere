const configuredBase = () =>
  (import.meta.env.VITE_API_BASE_URL || "").trim().replace(/\/$/, "");

/** URL for a path that already includes `/api`. Empty base keeps the Vite dev proxy. */
export function apiUrl(path: string): string {
  const base = configuredBase();
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (!base) return normalized;
  if (base.endsWith("/api")) return `${base.slice(0, -4)}${normalized}`;
  return `${base}${normalized}`;
}

/** Axios base for routes mounted under `/api`. */
export function newsApiBase(): string {
  const base = configuredBase();
  if (!base) return "/api";
  if (base.endsWith("/api")) return base;
  return `${base}/api`;
}
