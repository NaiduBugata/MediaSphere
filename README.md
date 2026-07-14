# MediaSphere

MediaSphere is an AI-powered constituency news monitoring platform for Narasaraopet. It collects local Telugu news from Lokal and YouTube, analyzes it with Groq, stores categorized articles in MongoDB, serves the data through a Flask API, displays it in a React dashboard, sends report emails, and exposes a production WhatsApp Cloud API webhook for Meta events.

## Architecture

```text
Lokal source    -> Collector -> AI Analyzer -> MongoDB -> Flask API -> React Dashboard
YouTube source  -> Collector -> AI Analyzer -> MongoDB -> Flask API -> React Dashboard
Meta WhatsApp   -> GET/POST /webhook        -> MongoDB webhook event log
Flask service   -> WhatsApp Graph API       -> outbound WhatsApp messages
```

1. **Lokal collector** (`server/lokal_collector.py`) fetches the rolling 7-day news window from the Lokal API.
2. **YouTube collector** (`server/youtube/`) searches YouTube by constituency keywords, fetches Telugu captions, and filters news content.
3. **Analyzer** (`server/telugu_ai_news_analyzer.py`) performs Groq-backed multi-stage categorization (shared by both sources).
4. **Storage** (`server/mongo_store.py`) upserts categorized articles into MongoDB by `post_id` (`lokal` numeric id or `yt_{video_id}`) with a `source` field.
5. **API** (`server/api_server.py`) serves the dashboard and report endpoints (`?source=lokal|youtube|all`).
6. **Dashboard** (`client/`) is a Vite + React + Tailwind + Recharts SPA with source filters and badges.
7. **Reports** (`server/reports/`) generate and email the daily 07:00 IST executive report and incremental per-article alerts.
8. **WhatsApp webhook** (`server/whatsapp/`) verifies Meta webhooks, receives message/status events, logs structured JSON, persists events, and provides `send_text_message()`.
9. **Pipeline reliability** (`server/pipeline_scheduler.py`, `pipeline_state.py`) runs Lokal+YouTube inside the Render Free web process with MongoDB scheduler state, distributed locks, catch-up, and history.

```text
API boot -> validate config -> self-test -> APScheduler (once)
         -> catch-up if last_success stale
         -> acquire Mongo pipeline_lock -> combined cycle -> history + state
```

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
│   ├── pipeline_scheduler.py #   Render Free in-process scheduler
│   ├── pipeline_state.py     #   Mongo scheduler_state / lock / history
│   ├── pipeline_config.py    #   pipeline env validation
│   ├── retry_utils.py        #   exponential backoff helper
│   ├── reports/            #   daily + incremental email reports package
│   ├── whatsapp/           #   WhatsApp Cloud API webhook + send service
│   ├── tests/              #   unit tests
│   ├── requirements.txt
│   └── .env.example        #   Groq, MongoDB, SMTP, scheduler config
├── render.yaml             #   Render Free blueprint (gunicorn --workers 1)
├── README.md
├── LICENSE
└── .gitignore
```

## Pipeline Reliability (Render Free)

Render Free does **not** support background workers and web services sleep after ~15 minutes of idle traffic. MediaSphere keeps the existing architecture and hardens the in-process scheduler:

- **Single scheduler:** APScheduler starts once (`Scheduler initialized successfully.` / `Scheduler already running.`).
- **Mongo state:** `scheduler_state` stores `last_success` (no ephemeral files).
- **Distributed lock:** `pipeline_lock` prevents overlapping catch-up and multi-process runs.
- **Smart catch-up:** on boot, runs once only if `last_success` is missing or older than `PIPELINE_INTERVAL_HOURS`.
- **History:** every run is recorded in `pipeline_history`.
- **Health:** `GET /api/pipeline/health`, `GET /api/database/health`, expanded `GET /api/health`.
- **Dedup:** unique `post_id` plus sparse unique `content_fingerprint`.
- **Dashboard:** `/api/news` returns `Cache-Control: no-store` and `data_revision`; client polls every 5 minutes and on focus.

### Known limitations

- Sleep still requires an inbound request (dashboard polling helps keep the service awake).
- gunicorn must stay at `--workers 1` (Mongo lock mitigates mistakes; single worker remains the rule).
- Catch-up is best-effort on cold start, not continuous collection while asleep.

## Endpoints

- `GET /api/news` — all categorized articles, newest first (`?source=lokal|youtube|all`) + `data_revision`
- `GET /api/news/stats` — aggregated statistics
- `GET /api/health` — liveness (+ mongo bool)
- `GET /api/pipeline/health` — scheduler diagnostics
- `GET /api/database/health` — Mongo diagnostics (no URI)
- `POST /api/pipeline/run-now` — admin manual trigger (`X-Pipeline-Admin-Token`) when `PIPELINE_ADMIN_TOKEN` is set
- `GET /api/reports/history` — daily report delivery history (newest first)
- `GET /api/reports/<id>` — a single report record (by `_id` or `YYYY-MM-DD` date)
- `POST /api/reports/send-now` — generate & send (body: `{"date": "YYYY-MM-DD", "force": false}`; de-dup applies)
- `POST /api/reports/regenerate` — force regenerate & resend (body: `{"date": "YYYY-MM-DD"}`)
- `GET /webhook` — Meta WhatsApp webhook verification
- `POST /webhook` — Meta WhatsApp incoming messages/status callbacks

`api_server.py` starts report and pipeline schedulers only when the matching environment flags are enabled.

## Requirements

- Python 3.10+
- Node.js 18+
- A MongoDB Atlas cluster
- One or more Groq API keys
- YouTube Data API v3 key (for YouTube pipeline; separate from Lokal)
- Meta WhatsApp Cloud API app credentials (for `/webhook` and outbound messages)

## Backend Setup

All backend commands run from the `server/` directory.

```bash
cd server
pip install -r requirements.txt
copy .env.example .env   # Windows  (use `cp` on macOS/Linux)
```

Fill in only real values in `.env`. Never commit `.env`; it is ignored by Git.

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
PIPELINE_ON_API=true
PIPELINE_CATCHUP_ON_START=true
PIPELINE_INTERVAL_HOURS=1
```

### Run the API server

```bash
python api_server.py
```

## WhatsApp Cloud API Webhook

The webhook is integrated into the existing Flask app with a Blueprint. It does not create a second Flask app or change any existing `/api/*` route.

### Callback URL

```text
https://mediasphere-1.onrender.com/webhook
```

### Meta verification

Set a secret verify token in Render:

```text
WHATSAPP_VERIFY_TOKEN=<choose-a-random-verify-token>
```

In Meta Developer Console, use the same value. Meta calls:

```text
GET /webhook?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>
```

Expected response: HTTP `200` with the raw challenge body. Wrong tokens return HTTP `403`.

### Events handled

`POST /webhook` returns `EVENT_RECEIVED` with HTTP `200` for valid webhook payloads. Fatal malformed JSON returns HTTP `400`.

Supported parsing includes:

- Incoming text, image, document, audio, video, sticker, contacts, and location messages
- Interactive replies: button replies, list replies, and legacy button replies
- Status callbacks: sent, delivered, read, and failed
- Delivery and read receipts
- Media IDs
- Template status updates
- Webhook-level errors and unknown event types

Webhook events are logged as structured JSON and persisted in MongoDB collection `whatsapp_webhook_events` using the existing `mongo_store` MongoDB client.

### Outbound WhatsApp text message

Use the reusable service:

```python
from whatsapp import send_text_message

send_text_message("919876543210", "Hello from MediaSphere")
```

Or use cURL directly:

```bash
curl -X POST "https://graph.facebook.com/v25.0/$WHATSAPP_PHONE_NUMBER_ID/messages" \
  -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": "919876543210",
    "type": "text",
    "text": {"preview_url": false, "body": "Hello from MediaSphere"}
  }'
```

### Example inbound payload

```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "123456789",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "15551234567",
          "phone_number_id": "987654321"
        },
        "contacts": [{
          "profile": {"name": "Test User"},
          "wa_id": "919876543210"
        }],
        "messages": [{
          "from": "919876543210",
          "id": "wamid.example",
          "timestamp": "1710000000",
          "type": "text",
          "text": {"body": "Hello MediaSphere"}
        }]
      },
      "field": "messages"
    }]
  }]
}
```

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

- **AI:** `GROQ_API_KEY`, `GROQ_API_KEYS`, `GROQ_API_KEY_*`, `GROQ_MODEL`, `GROQ_TIMEOUT_SECONDS`
- **MongoDB:** `MONGODB_URI`, `MONGODB_DB_NAME`, `MONGODB_COLLECTION`
- **API:** `API_HOST`, `API_PORT`, `API_DEBUG`, `CORS_ORIGINS`
- **Pipeline:** `PIPELINE_ON_API`, `PIPELINE_CATCHUP_ON_START`, `PIPELINE_INTERVAL_HOURS`, `PIPELINE_LOCK_TTL_SECONDS`, `PIPELINE_ADMIN_TOKEN`, `YOUTUBE_ENABLED`, `YOUTUBE_API_KEY`
- **Email/Reports:** `EMAIL_ENABLED`, `EMAIL_PROVIDER`, `RESEND_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `REPORT_RECIPIENTS`, `REPORT_ENABLED`, `REPORT_TIMEZONE`, `REPORT_HOUR`, `REPORT_MINUTE`
- **WhatsApp:** `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WABA_ID`, `WHATSAPP_GRAPH_API_VERSION`, `WHATSAPP_WEBHOOK_ENABLED`
- **Frontend (`client/.env`):** `VITE_API_BASE_URL` (defaults to `/api`, proxied to the Flask server in development).

## Render Deployment

The repository includes `render.yaml` for the Flask backend.

Backend service settings:

- **Root directory:** `server`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:$PORT wsgi:app`
- **Health check:** `/api/health`
- **Python:** `3.11.9`

Render free tier does not support background workers. The news pipeline runs inside the web service when `PIPELINE_ON_API=true`. Keep `--workers 1` so only one scheduler instance exists.

Add secrets in Render Dashboard, not in `render.yaml`:

```text
GROQ_API_KEY_1
MONGODB_URI
YOUTUBE_API_KEY
RESEND_API_KEY
SMTP_USERNAME
SMTP_PASSWORD
WHATSAPP_VERIFY_TOKEN
WHATSAPP_ACCESS_TOKEN
WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_WABA_ID
```

Frontend deployment:

```bash
cd client
npm install
npm run build
```

Serve `client/dist/` on Vercel/Netlify/static hosting and set `VITE_API_BASE_URL` to the deployed Flask API origin plus `/api` if needed.

## Meta Configuration

In Meta Developer Console:

1. Open the WhatsApp app.
2. Go to WhatsApp → Configuration.
3. Set callback URL to `https://mediasphere-1.onrender.com/webhook`.
4. Set verify token to the exact Render value of `WHATSAPP_VERIFY_TOKEN`.
5. Subscribe to `messages`.
6. Save and verify.
7. Send an inbound message to the business number and confirm Render logs plus MongoDB `whatsapp_webhook_events`.

## Legacy CSV pipeline

`server/orchestrator.py`, `server/run_pipeline.py`, and `server/lokal_news_collector.py` implement an earlier CSV-based pipeline retained for reference and covered by `server/tests/`.

## Tests

```bash
cd server
python -m unittest discover -s tests
```

Targeted WhatsApp tests:

```bash
cd server
python -m unittest tests.test_whatsapp_webhook -v
```

Manual verification after deployment:

```bash
curl "https://mediasphere-1.onrender.com/webhook?hub.mode=subscribe&hub.verify_token=$WHATSAPP_VERIFY_TOKEN&hub.challenge=test123"
```

Expected response body: `test123`.

## Troubleshooting

- **`/webhook` returns 404:** Render is still on an older deploy. Trigger Manual Deploy → Deploy latest commit.
- **Meta verification returns 403:** `WHATSAPP_VERIFY_TOKEN` in Render does not match Meta.
- **POST webhook returns 400:** Request body is missing or malformed JSON.
- **Outbound send returns token error:** Refresh or replace `WHATSAPP_ACCESS_TOKEN`.
- **Outbound send returns 429/rate limit:** Slow retries and check Meta app quota.
- **Events are accepted but not stored:** Check `MONGODB_URI` and Render logs for `whatsapp.db` errors. The webhook still returns `EVENT_RECEIVED` so Meta does not retry due to database outages.
- **Pipeline does not auto-update on Render free:** Keep `PIPELINE_ON_API=true`, `PIPELINE_CATCHUP_ON_START=true`, and a single gunicorn worker.

## Production Checklist

- [ ] `server/.env` and local secrets are not committed
- [ ] Render has all required AI, MongoDB, email, YouTube, and WhatsApp env vars
- [ ] `/api/health` returns HTTP 200
- [ ] `/webhook` passes Meta verification
- [ ] `POST /webhook` returns `EVENT_RECEIVED`
- [ ] WhatsApp events appear in `whatsapp_webhook_events`
- [ ] `python -m unittest discover -s tests` passes
- [ ] Frontend `npm run build` passes
- [ ] Render start command uses `gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:$PORT wsgi:app`

## License

MIT (see `LICENSE`).
