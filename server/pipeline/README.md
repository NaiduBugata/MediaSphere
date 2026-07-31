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
