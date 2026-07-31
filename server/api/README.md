# api/

Flask REST API for the MediaSphere constituency news dashboard.

| File | Purpose |
|------|---------|
| `app.py` | Flask application with all routes and CORS configuration |

## Endpoints

- `GET /api/news` — Categorized articles (filterable by source)
- `GET /api/news/stats` — Aggregated statistics
- `GET /api/health` — Liveness probe
- `GET /api/pipeline/health` — Scheduler diagnostics
- `GET /api/database/health` — MongoDB connectivity
- `POST /api/pipeline/run-now` — Admin manual trigger
- `GET /api/reports/history` — Report delivery history
- `POST /api/reports/send-now` — Generate and send report
