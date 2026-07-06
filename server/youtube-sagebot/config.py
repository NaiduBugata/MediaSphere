"""Pipeline configuration — loads keys from server/.env or local .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

SAGEBOT_DIR = Path(__file__).resolve().parent
SERVER_DIR = SAGEBOT_DIR.parent

load_dotenv(SERVER_DIR / ".env")
load_dotenv(SAGEBOT_DIR / ".env")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY_1", "")

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

MAX_RESULTS_PER_KEYWORD = int(os.getenv("YOUTUBE_MAX_RESULTS_PER_KEYWORD", "50"))
SEARCH_PERIOD_DAYS = int(os.getenv("YOUTUBE_SEARCH_PERIOD_DAYS", "2"))

TRANSCRIPT_LANGUAGES = ["te"]

DATA_DIR = SAGEBOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PIPELINE_LOG = DATA_DIR / "pipeline.log"
VIDEOS_JSON = DATA_DIR / "videos.json"
TRANSCRIPTS_JSON = DATA_DIR / "transcripts.json"
CLEAN_TRANSCRIPTS_JSON = DATA_DIR / "clean_transcripts.json"
ARTICLES_JSON = DATA_DIR / "articles.json"
NEWS_JSON = DATA_DIR / "news.json"
LATEST_NEWS_TXT = DATA_DIR / "latest_news.txt"

SIMILARITY_THRESHOLD = 0.85
MAX_ARTICLES_PER_RUN = 10
