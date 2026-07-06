# MediaSphere — AI-Powered MP Constituency News Monitoring

MediaSphere is an end-to-end system that collects local Telugu news for the Narasaraopet constituency, categorizes it with an AI pipeline (sentiment, category, location, entities, keywords), stores the results in MongoDB, and surfaces them through an executive, MP-first analytics dashboard.

## Architecture

```
Lokal source  ->  Collector  ->  AI Analyzer  ->  MongoDB (MediaSphere)  ->  Flask API  ->  React Dashboard
YouTube source ->  Collector  ->  (same analyzer)  ->  (same MongoDB/API/dashboard)
```

1. **Lokal collector** (`server/lokal_collector.py`) fetches the rolling 7-day news window from the Lokal API.
2. **YouTube collector** (`server/youtube/`) searches YouTube by constituency keywords, fetches Telugu captions, and filters news content.
3. **Analyzer** (`server/telugu_ai_news_analyzer.py`) performs Groq-backed multi-stage categorization (shared by both sources).
4. **Storage** (`server/mongo_store.py`) upserts categorized articles into MongoDB by `post_id` (`lokal` numeric id or `yt_{video_id}`) with a `source` field.
5. **API** (`server/api_server.py`) serves the dashboard and report endpoints (`?source=lokal|youtube|all`).
6. **Dashboard** (`client/`) is a Vite + React + Tailwind + Recharts SPA with source filters and badges.
7. **Reports** (`server/reports/`) generate and email the daily 07:00 IST executive report and incremental per-article alerts.

The combined pipeline runner (`server/run_all_pipelines.py`) runs Lokal then YouTube every hour when `YOUTUBE_ENABLED=true`.

## Project Structure

```
.
├── client/                 # Frontend — Vite + React + Tailwind SPA
│   ├── src/                #   components, hooks, services, utils
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js      #   dev proxy /api -> http://localhost:5000
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── .env.example        #   VITE_API_BASE_URL
├── server/                 # Backend — Python (Flask API, AI pipeline, scheduler)
│   ├── api_server.py       #   Flask API + report admin routes + scheduler boot
│   ├── run_lokal_analysis.py  # Lokal pipeline runner
│   ├── run_youtube_analysis.py  # YouTube pipeline runner
│   ├── run_all_pipelines.py   # Combined Lokal + YouTube worker entry
│   ├── youtube/            #   Integrated YouTube collector (MediaSphere pipeline)
│   ├── youtube-sagebot/    #   Standalone Sagebot tools (export, dedup, CLI)
│   ├── lokal_collector.py  #   Lokal news collector
│   ├── telugu_ai_news_analyzer.py  # Groq categorization
│   ├── mongo_store.py      #   MongoDB persistence + admin CLI
│   ├── generate_article_txt.py
│   ├── config.py           #   pipeline paths/config
│   ├── reports/            #   daily + incremental email reports package
│   ├── tests/              #   unit tests (legacy CSV pipeline)
│   ├── requirements.txt
│   └── .env.example        #   Groq, MongoDB, SMTP, scheduler config
├── README.md
├── LICENSE
└── .gitignore
```

## Requirements

- Python 3.10+
- Node.js 18+
- A MongoDB Atlas cluster
- One or more Groq API keys
- YouTube Data API v3 key (for YouTube pipeline; separate from Lokal)

## Backend Setup

All backend commands run from the `server/` directory.

```bash
cd server
pip install -r requirements.txt
copy .env.example .env   # Windows  (use `cp` on macOS/Linux); then fill in GROQ + MONGODB + SMTP values
```

### Run the pipeline

```bash
python run_all_pipelines.py --once   # Lokal + YouTube (if YOUTUBE_ENABLED=true)
python run_all_pipelines.py          # continuous, every 1 hour

python run_lokal_analysis.py --once   # Lokal only
python run_youtube_analysis.py --once # YouTube only (requires YOUTUBE_API_KEY)
```

Set in `.env`:

```
YOUTUBE_ENABLED=true
YOUTUBE_API_KEY=your_youtube_data_api_key
```

### Run the API server

```bash
python api_server.py
```

Endpoints:
- `GET /api/news` — all categorized articles, newest first (`?source=lokal|youtube|all`)
- `GET /api/news/stats` — aggregated statistics
- `GET /api/health` — health check
- `GET /api/reports/history` — daily report delivery history (newest first)
- `GET /api/reports/<id>` — a single report record (by `_id` or `YYYY-MM-DD` date)
- `POST /api/reports/send-now` — generate & send (body: `{"date": "YYYY-MM-DD", "force": false}`; de-dup applies)
- `POST /api/reports/regenerate` — force regenerate & resend (body: `{"date": "YYYY-MM-DD"}`)

Starting `api_server.py` also boots the daily report scheduler (07:00 IST) with a one-time catch-up for any missed run.

### MongoDB admin

```bash
python mongo_store.py --stats            # document count
python mongo_store.py --reset            # archive + clear active collection
python mongo_store.py --reset --no-archive
```

## Daily Constituency Intelligence Report

An automated report of the **previous day's** news (00:00–23:59 IST) is generated and emailed to the configured recipients every day at **07:00 AM IST**. It includes an AI executive summary (Groq, with a deterministic fallback), key metrics, top 10 action-required issues, top 10 positive developments, category/location/sentiment summaries, top keywords/entities, and a full article digest. Delivery is a branded HTML email with a `Daily_Report_YYYY_MM_DD.pdf` attachment.

- **Scheduler:** APScheduler cron at 07:00 IST; on startup it sends any missed report once (catch-up).
- **De-duplication:** the `daily_reports` collection keys on `report_date`, so no day is emailed twice.
- **Resilience:** email failures are retried with backoff, logged, and never crash the app.
- **Modules:** `reports/config.py`, `logger.py`, `data_service.py`, `ai_summary.py`, `html_template.py`, `pdf_generator.py`, `email_service.py`, `db_service.py`, `report_generator.py`, `scheduler.py`.

Configure SMTP and recipients in `.env` (see `.env.example`). For Gmail, use an App Password.

```bash
python -m reports send-now                 # send yesterday's report (de-dup applies)
python -m reports send-now --force         # regenerate & resend even if already sent
python -m reports send-now --date 2026-07-03
python -m reports build --date 2026-07-03  # build HTML + PDF only (no email)
python -m reports history                  # show delivery history
```

> For multi-worker WSGI deployments (e.g. gunicorn), run the scheduler as a single dedicated process rather than per worker to avoid concurrent generation. De-duplication still protects the database record either way.

### Incremental hourly update emails

After every pipeline cycle (collect → categorize → store), an email is sent containing **only the newly inserted articles** that have not been emailed before. This is separate from — and does not replace — the 07:00 daily executive report.

- **Trigger:** runs automatically at the end of `run_cycle()` once articles are stored. If no un-emailed articles exist, it logs `No new articles collected during this cycle.` and sends nothing.
- **Subject:** `MediaSphere News Update | DD MMM YYYY | HH:MM IST`.
- **Content:** short executive summary, six summary metrics, and one professional card per article (title, AI summary, category/subcategory, sentiment, district/mandal/village, published time, source link). Problem/Negative articles get a red-bordered card with problem summary, responsible department, priority, and action required.
- **Duplicate prevention:** each document carries `email_sent`, `email_sent_at`, and `email_batch_id`. New articles are inserted with `email_sent=false`; only `email_sent=false` articles are emailed, and they are flipped to `true` **only after a successful send**. Failed sends leave the articles pending so they retry next cycle.

> Selection uses plain equality (`email_sent: false`) rather than `$exists`/`$ne`, because the Atlas cluster in use does not honour those operators.

Manual controls:

```bash
python -m reports send-incremental        # email pending (not-yet-emailed) articles now
python -m reports backfill-flags          # mark legacy docs as already emailed (production default)
python -m reports backfill-flags --pending # mark legacy docs as pending (one-off catch-up)
```

## Frontend Setup

All frontend commands run from the `client/` directory.

```bash
cd client
npm install
copy .env.example .env
npm run dev      # http://localhost:5173 (proxies /api to :5000)
npm run build    # production build to client/dist
npm run preview  # preview the production build
```

## Dashboard Features

- MP-first layout: summary cards, priority problems, action-required issues, positive developments
- Analytics: sentiment/category pies, daily trend, category/mandal/village bars
- Searchable, filterable, sortable, paginated news table
- Article detail modal with highlighted AI summary and recommended action
- Loading, skeleton, empty, and error states; fully responsive

## Environment Variables

See `server/.env.example` (backend) and `client/.env.example` (frontend). Secrets are never committed; `.env` files are gitignored.

- **Backend (`server/.env`):** `GROQ_API_KEY_*`, `MONGODB_URI`, `MONGODB_DB_NAME`, `MONGODB_COLLECTION`, `API_HOST`/`API_PORT`/`API_DEBUG`, `CORS_ORIGINS`, SMTP settings (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, ...), `REPORT_RECIPIENTS`, and scheduler settings (`REPORT_ENABLED`, `REPORT_TIMEZONE`, `REPORT_HOUR`, `REPORT_MINUTE`).
- **Frontend (`client/.env`):** `VITE_API_BASE_URL` (defaults to `/api`, proxied to the Flask server in development).

## Deployment

1. **Backend:** from `server/`, install `requirements.txt` and serve `api_server.py` behind a production WSGI server (e.g. `gunicorn api_server:app`). Provide `server/.env`. Run the pipeline (`run_lokal_analysis.py`) as a long-running process or scheduled job. In multi-worker setups, run the report scheduler as a single dedicated process (de-duplication protects the DB record regardless).
2. **Frontend:** from `client/`, run `npm run build` and serve `client/dist/` as static files (Netlify, Vercel, Nginx, etc.). Set `VITE_API_BASE_URL` to the deployed API origin.

## Legacy CSV pipeline

`server/orchestrator.py`, `server/run_pipeline.py`, and `server/lokal_news_collector.py` implement an earlier CSV-based pipeline retained for reference and covered by `server/tests/`.

## Tests

```bash
cd server
python -m unittest discover -s tests
```

## License

MIT (see `LICENSE`).
