# YouTube integration (MediaSphere)

This folder powers the **integrated** YouTube pipeline used by the dashboard.

| Module | Role |
|--------|------|
| `config.py` | Env vars, keywords, paths under `server/data/youtube/` |
| `search.py` | YouTube Data API search |
| `transcripts.py` | Telugu caption fetch |
| `clean.py` | News filtering |
| `collector.py` | Orchestrates search → transcripts → `youtube_news.json` |

## Run (production)

From `server/`:

```bash
python run_youtube_analysis.py --once
python run_all_pipelines.py --once   # Lokal + YouTube
```

Data output: `server/data/youtube/`

## Standalone tools

For export, deduplication, and full Sagebot CLI, see **`../youtube-sagebot/`** (kept separately).
