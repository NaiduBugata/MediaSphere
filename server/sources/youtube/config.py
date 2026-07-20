"""YouTube pipeline configuration (env-driven, separate from Lokal)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# server/ directory (three levels above sources/youtube/config.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "youtube"

YOUTUBE_ENABLED = os.getenv("YOUTUBE_ENABLED", "true").lower() in ("1", "true", "yes", "on")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_PERIOD_DAYS = int(os.getenv("YOUTUBE_SEARCH_PERIOD_DAYS", "2"))
YOUTUBE_MAX_RESULTS_PER_KEYWORD = int(os.getenv("YOUTUBE_MAX_RESULTS_PER_KEYWORD", "50"))
YOUTUBE_CHECK_INTERVAL = int(os.getenv("YOUTUBE_CHECK_INTERVAL", "3600"))
YOUTUBE_MAX_NEW_PER_RUN = int(os.getenv("YOUTUBE_MAX_NEW_PER_RUN", "30"))
YOUTUBE_MIN_CONTENT_CHARS = int(os.getenv("YOUTUBE_MIN_CONTENT_CHARS", "100"))
YOUTUBE_MAX_CONTENT_CHARS = int(os.getenv("YOUTUBE_MAX_CONTENT_CHARS", "6000"))

TRANSCRIPT_LANGUAGES = ["te"]

SEARCH_KEYWORDS = [
    "నరసరావుపేట",
    "పల్నాడు",
    "Narasaraopet",
    "Palnadu",
    "చిలకలూరిపేట",
    "సత్తెనపల్లి",
    "వినుకొండ",
    "Chilakaluripet",
    "Sattenapalli",
    "Vinukonda",
    "పిడుగురాళ్ళ",
    "Piduguralla",
    "మాచర్ల",
    "Macherla",
    "రొంపిచర్ల",
    "Rompicherla",
]

KEYWORDS = SEARCH_KEYWORDS

VIDEOS_JSON = DATA_DIR / "videos.json"
TRANSCRIPTS_JSON = DATA_DIR / "transcripts.json"
NEWS_JSON = DATA_DIR / "youtube_news.json"
PIPELINE_LOG = DATA_DIR / "pipeline.log"
ARTICLE_PATH = DATA_DIR / "article.txt"
OUTPUT_DIR = DATA_DIR / "output"
CHECKPOINT_FILE = DATA_DIR / "checkpoint.json"
