# Ensure automatic daily pipeline auth (Render + GitHub)

Production `POST /api/pipeline/run-now` returns **503** until at least one of these is set on Render:

- `PIPELINE_ADMIN_TOKEN`
- `ADMIN_PASSWORD` (API accepts this as a fallback after commit `3f9dd34`)

## Steps (do once)

1. Generate a token:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/generate_pipeline_admin_token.ps1 -WriteEnv
   ```
2. **Render** → `mediasphere-api` → Environment:
   - Set `PIPELINE_ADMIN_TOKEN` = that token
   - Set `ADMIN_USERNAME` / `ADMIN_PASSWORD` for `/@admin` (recommended)
   - Save → wait for deploy (or **Manual Deploy** latest `main`)
3. **GitHub** → Settings → Secrets and variables → Actions:
   - `PIPELINE_ADMIN_TOKEN` = **same** token
   - Optional: `ADMIN_PASSWORD` = same as Render
   - Optional: `PIPELINE_BASE_URL` = `https://mediasphere-1.onrender.com`
4. Verify:
   ```powershell
   $env:PIPELINE_ADMIN_TOKEN = "<token>"
   powershell -ExecutionPolicy Bypass -File scripts/check_pipeline_cron.ps1
   ```
   Expect run-now **202** (not 503).
5. Actions → **Pipeline keep-alive** → Run workflow (trigger pipeline on) → `run-pipeline` must log `run_now_http=202`.

## Why news went stale

- Keep-alive health pings were working, but hourly run-now was a **false green** (missing secret → exit 0 skip). Fixed to **fail** when secrets are missing (`23454db`).
- Render Free still needs the 10‑minute wake; GitHub cron can be delayed — add cron-job.org health ping if wakes are sparse.
- Cycles often **update** existing rows (`inserted=0`) when sources have no brand-new posts; that is normal. New inserts appear when collectors find new URLs/videos.
