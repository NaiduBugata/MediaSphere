# MediaSphere — AI-Powered MP Constituency News Monitoring

MediaSphere is an end-to-end system that collects local Telugu news for the Narasaraopet constituency, categorizes it with an AI pipeline (sentiment, category, location, entities, keywords), stores the results in MongoDB, and surfaces them through an executive, MP-first analytics dashboard.

## Architecture

```
Lokal source  ->  Collector  ->  AI Analyzer  ->  MongoDB (MediaSphere)  ->  Flask API  ->  React Dashboard
```

1. **Collector** (`lokal_collector.py`) fetches the rolling 7-day news window from the Lokal API.
2. **Analyzer** (`telugu_ai_news_analyzer.py`) performs Groq-backed multi-stage categorization.
3. **Storage** (`mongo_store.py`) upserts categorized articles into MongoDB by Lokal `post_id` (no duplicates).
4. **API** (`api_server.py`) serves `GET /api/news` and `GET /api/news/stats`.
5. **Dashboard** (`dashboard/`) is a Vite + React + Tailwind + Recharts SPA that computes stats client-side.

The pipeline runner (`run_lokal_analysis.py`) chains collection -> analysis -> storage and can run once or continuously every 4 hours.

## Requirements

- Python 3.10+
- Node.js 18+
- A MongoDB Atlas cluster
- One or more Groq API keys

## Backend Setup

```bash
pip install -r requirements.txt
copy .env.example .env   # then fill in GROQ + MONGODB values
```

### Run the pipeline

```bash
python run_lokal_analysis.py --once   # single cycle (collect -> analyze -> store)
python run_lokal_analysis.py          # continuous, every 4 hours
```

### Run the API server

```bash
python api_server.py
```

Endpoints:
- `GET /api/news` — all categorized articles, newest first
- `GET /api/news/stats` — aggregated statistics
- `GET /api/health` — health check

### MongoDB admin

```bash
python mongo_store.py --stats            # document count
python mongo_store.py --reset            # archive + clear active collection
python mongo_store.py --reset --no-archive
```

## Frontend Setup

```bash
cd dashboard
npm install
copy .env.example .env
npm run dev      # http://localhost:5173 (proxies /api to :5000)
npm run build    # production build to dashboard/dist
```

## Dashboard Features

- MP-first layout: summary cards, priority problems, action-required issues, positive developments
- Analytics: sentiment/category pies, daily trend, category/mandal/village bars
- Searchable, filterable, sortable, paginated news table
- Article detail modal with highlighted AI summary and recommended action
- Loading, skeleton, empty, and error states; fully responsive

## Environment Variables

See `.env.example` (backend) and `dashboard/.env.example` (frontend). Secrets are never committed; `.env` files are gitignored.

## Legacy CSV pipeline

`orchestrator.py`, `run_pipeline.py`, and `lokal_news_collector.py` implement an earlier CSV-based pipeline retained for reference and covered by `tests/`.

## Tests

```bash
python -m unittest discover -s tests
```

## License

MIT (see `LICENSE`).
