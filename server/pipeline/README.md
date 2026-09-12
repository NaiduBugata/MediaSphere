# pipeline/

Pipeline orchestration: scheduling, running, state management, and health.

| File | Purpose |
|------|---------|
| `scheduler.py` | APScheduler-based in-process job scheduler |
| `runner.py` | Combined cycle runner (Lokal + YouTube + Sakshi) |
| `state.py` | MongoDB-backed pipeline state persistence |
| `config.py` | Pipeline-specific configuration |
| `retry.py` | Exponential backoff retry utility |
| `lokal_runner.py` | Lokal source analysis runner |
| `youtube_runner.py` | YouTube source analysis runner |
| `sakshi_runner.py` | Sakshi source analysis runner |

## Architecture

The pipeline scheduler triggers `run_combined_cycle()` at configurable intervals.
Each source runner: collects articles → generates article.txt → runs AI analyzer → upserts to MongoDB.

Interval is controlled by `PIPELINE_INTERVAL_HOURS` (default **1 hour** in production).
There is no built-in 4-hour schedule unless you set that env var.

## Render Free sleep (why fetches go stale)

On Render’s **free** web plan the dyno **sleeps after ~15 minutes with no HTTP traffic**.
The news pipeline runs **inside** that same process (`PIPELINE_ON_API=true`), so when the
service sleeps:

- APScheduler is stopped
- Hourly interval jobs are **missed**
- Collection resumes only on the next cold start (catch-up if `last_success` is stale)

Dashboard UI polling (`GET /api/news` every 5 minutes) only **reads** MongoDB; it does
not collect news. If nobody has the site open, the dyno sleeps and data goes stale.

## External keep-alive + run-now (required on Free)

Use wall-clock HTTP so Render wakes even with no browser open.

### 1. Set `PIPELINE_ADMIN_TOKEN` on Render

1. Open [Render Dashboard](https://dashboard.render.com) → service `mediasphere-api` → **Environment**
2. Add or copy `PIPELINE_ADMIN_TOKEN` (long random string; Blueprint may `generateValue` on first sync)
3. Save / redeploy so the web process picks it up
4. Confirm: `POST /api/pipeline/run-now` without the header returns **403**, not **503**

Without this env var, `POST /api/pipeline/run-now` returns `503` (`PIPELINE_ADMIN_TOKEN is not configured`).

### 2. GitHub Actions (in this repo)

Workflow: [`.github/workflows/pipeline-keepalive.yml`](../../.github/workflows/pipeline-keepalive.yml)

| Schedule | Action |
|----------|--------|
| Every **10 minutes** | `GET /api/health` (keep-alive; prevents ~15 min sleep) |
| Every **hour** | `POST /api/pipeline/run-now` with admin token |

Repo secrets (GitHub → Settings → Secrets and variables → Actions):

| Secret | Value |
|--------|--------|
| `PIPELINE_BASE_URL` | `https://mediasphere-1.onrender.com` (optional; this is the default) |
| `PIPELINE_ADMIN_TOKEN` | **Same** value as Render `PIPELINE_ADMIN_TOKEN` |

After push, use **Actions → Pipeline keep-alive → Run workflow** once to verify.

### 3. Alternative: cron-job.org / EasyCron

If you prefer not to use GitHub Actions:

1. Job A — every **10 minutes**: `GET https://mediasphere-1.onrender.com/api/health`
2. Job B — every **1 hour**: `POST https://mediasphere-1.onrender.com/api/pipeline/run-now`  
   Header: `X-Pipeline-Admin-Token: <your token>`

### 4. Verify

```bash
curl -sS https://mediasphere-1.onrender.com/api/pipeline/health
```

Expect `scheduler: "running"`, fresh `last_success` / `last_run`, and `next_run` about one
interval ahead. After an idle period with keep-alive running, `last_success` should not
lag many hours behind wall clock.

## Manual trigger

```bash
curl -X POST https://mediasphere-1.onrender.com/api/pipeline/run-now \
  -H "X-Pipeline-Admin-Token: $PIPELINE_ADMIN_TOKEN"
```

Returns `202` when accepted.
