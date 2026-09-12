# Admin ops dashboard (`/@admin`)

Secure monitoring and manual recovery for the shared news pipeline.

## URL

Production: `https://media-sphere-omega.vercel.app/@admin`

## Auth

Set one of:

- `ADMIN_PASSWORD` (preferred), or
- `PIPELINE_ADMIN_TOKEN` (fallback login password)

Optional: `ADMIN_SESSION_SECRET`, `ADMIN_SESSION_TTL_SECONDS`.

Login issues a Bearer session token (HMAC). All `/api/admin/*` routes require it.

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/admin/auth/login` | password → token |
| POST | `/api/admin/auth/logout` | client discard |
| GET | `/api/admin/auth/me` | session check |
| GET | `/api/admin/fetch/status` | headline, freshness, alerts |
| POST | `/api/admin/fetch/trigger` | manual fetch (same `run_combined_cycle`) |
| POST | `/api/admin/fetch/retry/:runId` | retry failed run |
| GET | `/api/admin/fetch/history` | history + filters |
| GET | `/api/admin/fetch/:runId` | detail |
| GET | `/api/admin/scheduler/status` | interval / delay |
| GET | `/api/admin/health` | component health |

## Config

- `PIPELINE_INTERVAL_HOURS` / `FETCH_INTERVAL_HOURS` — expected cadence
- `FETCH_DELAY_TOLERANCE_MINUTES` — delay alert slack (default 30)

Manual and automatic triggers both use `pipeline_scheduler._job` → `run_combined_cycle` with Mongo `pipeline_lock`.
