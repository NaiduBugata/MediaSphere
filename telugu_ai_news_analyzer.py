"""Telugu OCR news analysis pipeline with deterministic post-processing and Groq-backed semantic analysis."""

from __future__ import annotations

import ast
import csv
import hashlib
import heapq
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import unicodedata
import uuid
from collections import Counter, defaultdict
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import orjson  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    orjson = None

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


# ===========================================================
# CONFIGURATION
# ===========================================================

APP_NAME = "Telugu AI News Analyzer"
RUN_ID = uuid.uuid4().hex
JSON_INDENT = 4

INPUT_FILE = Path(os.getenv("INPUT_FILE", "input.txt"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
INDIVIDUAL_OUTPUT_DIR = OUTPUT_DIR / "individual_articles"
ARTICLES_OUTPUT_DIR = OUTPUT_DIR / "articles"
CHECKPOINT_FILE = Path(os.getenv("CHECKPOINT_FILE", "checkpoint.json"))
ALL_ARTICLES_FILE = OUTPUT_DIR / "all_articles.json"
ALL_ARTICLES_CSV_FILE = OUTPUT_DIR / "all_articles.csv"
FAILED_ARTICLES_FILE = OUTPUT_DIR / "failed_articles.json"
PROCESSING_LOG_FILE = OUTPUT_DIR / "processing.log"

MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.0"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "120"))

DEFAULT_WORKERS = int(os.getenv("WORKERS", "5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
COOLDOWN_SECONDS = float(os.getenv("COOLDOWN_SECONDS", "60"))
EMPTY_ARTICLE_MIN_CHARS = int(os.getenv("EMPTY_ARTICLE_MIN_CHARS", "25"))

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_DUPLICATE = "duplicate"

ALLOWED_SENTIMENTS = {"Problem", "Positive", "Negative", "Statement"}
ALLOWED_CATEGORIES = {
    "Roads",
    "Drainage",
    "Water",
    "Electricity",
    "Agriculture",
    "Health",
    "Education",
    "Employment",
    "Government",
    "Politics",
    "Crime",
    "Court",
    "Revenue",
    "Transport",
    "Environment",
    "Weather",
    "Business",
    "Economy",
    "Sports",
    "Entertainment",
    "Religion",
    "Technology",
    "Social Welfare",
    "Infrastructure",
    "Public Grievance",
    "Tourism",
    "Other",
}


# ===========================================================
# OPTIONAL ENVIRONMENT LOADING
# ===========================================================


def _load_environment_files() -> None:
    """Load .env files using python-dotenv when available, with a safe fallback."""

    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"]
    loaded = False

    if load_dotenv is not None:
        for candidate in candidates:
            if candidate.exists():
                load_dotenv(dotenv_path=str(candidate), override=False)
                loaded = True

    if loaded:
        return

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            for raw_line in candidate.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except Exception:
            continue


_load_environment_files()


# ===========================================================
# JSON HELPERS
# ===========================================================


def _json_dumps(data: Any, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(data, ensure_ascii=False, indent=JSON_INDENT, sort_keys=False)
    if orjson is not None:
        return orjson.dumps(data).decode("utf-8")
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _json_loads(payload: str) -> Any:
    if orjson is not None:
        return orjson.loads(payload)
    return json.loads(payload)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".{RUN_ID}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    # On Windows, replace can fail due to file locks. Retry a few times,
    # then fall back to overwrite with remove+rename.
    import os
    import time

    for attempt in range(5):
        try:
            temp_path.replace(path)
            return
        except PermissionError:
            # brief backoff and retry
            time.sleep(0.05 * (attempt + 1))
            continue
        except Exception:
            # try a safe fallback: remove target if possible and rename
            try:
                if path.exists():
                    path.unlink()
                temp_path.replace(path)
                return
            except Exception:
                # last resort: write directly to path
                try:
                    path.write_text(content, encoding="utf-8")
                    if temp_path.exists():
                        temp_path.unlink()
                    return
                except Exception:
                    pass

    # If we get here, final attempt
    try:
        if path.exists():
            path.unlink()
        temp_path.replace(path)
    except Exception:
        # give up; let caller handle exceptions
        raise


def _atomic_write_json(path: Path, data: Any, *, pretty: bool = True) -> None:
    _atomic_write_text(path, _json_dumps(data, pretty=pretty))


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    return Normalizer.normalize_whitespace(value)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text.strip()))


def _extract_first_json_object(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    start_index = text.find("{")
    if start_index < 0:
        raise ValueError("No JSON object start found.")

    depth = 0
    in_string = False
    escape = False
    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    raise ValueError("No complete JSON object found.")


# ===========================================================
# DETERMINISTIC NORMALIZATION
# ===========================================================


class Normalizer:
    """Normalize OCR text, model output, and deterministic fields in a single place."""

    _DASH_LINE = re.compile(r"(?m)^[\s\-‐‑‒–—−]{20,}\s*$")
    _MULTI_BLANK_LINES = re.compile(r"(?:\n\s*){3,}")
    _WHITESPACE = re.compile(r"\s+")
    _PUNCTUATION = re.compile(r"[\u200B\u200C\u200D\uFEFF\u2060\u00AD]")
    _TRAILING_COMMAS = re.compile(r",(?=\s*[}\]])")
    _DISTRICT_ALIASES = {
        "guntur": "Guntur",
        "గుంటూరు": "Guntur",
        "guntur జిల్లా": "Guntur",
        "గుంటూరు జిల్లా": "Guntur",
        "palnadu": "Palnadu",
        "పల్నాడు": "Palnadu",
        "palnadu జిల్లా": "Palnadu",
        "పల్నాడు జిల్లా": "Palnadu",
        "narasaraopet": "Palnadu",
        "నరసరావుపేట": "Palnadu",
    }
    _CATEGORY_MAP = {re.sub(r"[^a-z0-9]+", "", item.casefold()): item for item in ALLOWED_CATEGORIES}
    _CATEGORY_MATCHES = (
        ("roads", "Roads"),
        ("road", "Roads"),
        ("drainage", "Drainage"),
        ("water", "Water"),
        ("electricity", "Electricity"),
        ("power", "Electricity"),
        ("agriculture", "Agriculture"),
        ("health", "Health"),
        ("education", "Education"),
        ("educational", "Education"),
        ("school", "Education"),
        ("college", "Education"),
        ("విద్య", "Education"),
        ("employment", "Employment"),
        ("employ", "Employment"),
        ("job", "Employment"),
        ("labor", "Employment"),
        ("labour", "Employment"),
        ("jobs", "Employment"),
        ("government", "Government"),
        ("governance", "Government"),
        ("administration", "Government"),
        ("politics", "Politics"),
        ("election", "Politics"),
        ("crime", "Crime"),
        ("court", "Court"),
        ("revenue", "Revenue"),
        ("transport", "Transport"),
        ("rail", "Transport"),
        ("environment", "Environment"),
        ("weather", "Weather"),
        ("business", "Business"),
        ("economy", "Economy"),
        ("sports", "Sports"),
        ("entertainment", "Entertainment"),
        ("culture", "Other"),
        ("festival", "Religion"),
        ("religion", "Religion"),
        ("technology", "Technology"),
        ("social welfare", "Social Welfare"),
        ("social welfare", "Social Welfare"),
        ("welfare", "Social Welfare"),
        ("infrastructure", "Infrastructure"),
        ("grievance", "Public Grievance"),
        ("tourism", "Tourism"),
    )

    @classmethod
    def clean_ocr_text(cls, text: Any) -> str:
        if text is None:
            return ""
        value = unicodedata.normalize("NFKC", str(text))
        value = cls._PUNCTUATION.sub("", value)
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = cls._DASH_LINE.sub("----------------------------------------------------------------------------------------------------", value)
        value = re.sub(r"[ \t\f\v]+", " ", value)
        value = cls._MULTI_BLANK_LINES.sub("\n\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    @classmethod
    def normalize_whitespace(cls, text: Any) -> str:
        if text is None:
            return ""
        value = unicodedata.normalize("NFKC", str(text))
        value = cls._PUNCTUATION.sub("", value)
        value = cls._WHITESPACE.sub(" ", value)
        return value.strip()

    @classmethod
    def normalize_category(cls, value: Any) -> str:
        text = cls.normalize_whitespace(value)
        if not text:
            return "Other"
        # map common news-like aliases deterministically to Other
        if isinstance(text, str) and text.strip().casefold() in {"news", "వార్త", "announcement", "meeting"}:
            return "Other"

        normalized = re.sub(r"[^\w\u0C00-\u0C7F]+", " ", text.casefold())
        normalized = cls._WHITESPACE.sub(" ", normalized).strip()
        compact = re.sub(r"[^\w\u0C00-\u0C7F]+", "", normalized)

        direct = cls._CATEGORY_MAP.get(compact)
        if direct:
            return direct

        for token, category in cls._CATEGORY_MATCHES:
            if token in normalized or token.replace(" ", "") in compact:
                return category

        # Fallback: fuzzy match against allowed category names (ASCII-normalized)
        try:
            import difflib

            choices = list(cls._CATEGORY_MAP.values())
            # perform casefold matching
            matches = difflib.get_close_matches(text.casefold(), [c.casefold() for c in choices], n=1, cutoff=0.78)
            if matches:
                # find original-cased category
                for c in choices:
                    if c.casefold() == matches[0]:
                        return c
        except Exception:
            pass

        return cls._concisify_phrase(text, max_words=2) or "Other"

    @classmethod
    def _concisify_phrase(cls, value: Any, *, max_words: int) -> str:
        text = cls.normalize_whitespace(value)
        if not text:
            return ""
        words = [w for w in re.split(r"\s+", text) if w]
        concise = " ".join(words[:max_words])
        return concise

    @classmethod
    def normalize_subcategory(cls, value: Any) -> str:
        text = cls.normalize_whitespace(value)
        return cls._concisify_phrase(text, max_words=2)

    @classmethod
    def normalize_district(cls, value: Any) -> str:
        text = cls.normalize_whitespace(value)
        if not text:
            return ""
        key = re.sub(r"[^\w\u0C00-\u0C7F]+", " ", text.casefold())
        key = cls._WHITESPACE.sub(" ", key).strip()
        if key in cls._DISTRICT_ALIASES:
            return cls._DISTRICT_ALIASES[key]
        compact = re.sub(r"[^\w\u0C00-\u0C7F]+", "", key)
        if compact in cls._DISTRICT_ALIASES:
            return cls._DISTRICT_ALIASES[compact]
        if re.search(r"[A-Za-z]", text):
            return text[:1].upper() + text[1:].lower()
        return text

    @classmethod
    def normalize_location(cls, value: Any) -> Dict[str, Optional[str]]:
        location = value if isinstance(value, dict) else {}
        district_telugu = cls.normalize_whitespace(location.get("district_telugu") or location.get("district")) or None
        mandal_telugu = cls.normalize_whitespace(location.get("mandal_telugu") or location.get("mandal")) or None
        village_telugu = cls.normalize_whitespace(location.get("village_telugu") or location.get("village")) or None
        town_telugu = cls.normalize_whitespace(location.get("town_telugu") or location.get("town")) or None
        town = cls.normalize_whitespace(location.get("town")) or None
        mandal = cls.normalize_district(location.get("mandal") or mandal_telugu) or None
        district = cls.normalize_district(location.get("district") or district_telugu) or None
        state_telugu = cls.normalize_whitespace(location.get("state_telugu") or "ఆంధ్రప్రదేశ్") or None
        return {
            "village_telugu": village_telugu,
            "village": village_telugu,
            "town_telugu": town_telugu,
            "town": town,
            "mandal_telugu": mandal_telugu,
            "mandal": mandal,
            "district_telugu": district_telugu,
            "district": district,
            "state_telugu": state_telugu,
            "state": "Andhra Pradesh",
        }

    @classmethod
    def normalize_problem(cls, value: Any) -> Optional[str]:
        text = cls.normalize_whitespace(value)
        return text or None

    @classmethod
    def normalize_summary(cls, value: Any) -> str:
        text = cls.normalize_whitespace(value)
        return text

    @classmethod
    def normalize_title(cls, value: Any) -> str:
        return cls.normalize_whitespace(value)

    @classmethod
    def normalize_keywords(cls, value: Any) -> List[str]:
        return SummaryNormalizer.normalize_keywords(value)

    @classmethod
    def normalize_people(cls, value: Any) -> List[Dict[str, str]]:
        return SummaryNormalizer.normalize_people(value)

    @classmethod
    def normalize_entities(cls, value: Any) -> List[Dict[str, str]]:
        return SummaryNormalizer.normalize_entities(value)

    @classmethod
    def normalize_confidence(cls, value: Any) -> float:
        return SummaryNormalizer.normalize_confidence(value)

    @classmethod
    def normalize_json_candidate(cls, value: str) -> str:
        return SummaryNormalizer.normalize_json_candidate(value)


class SummaryNormalizer:
    """Clean and lightly validate summaries while preserving Telugu text.

    Responsibilities:
    - Trim whitespace and normalize unicode
    - Remove markdown, bullets and simple formatting
    - Collapse duplicate punctuation and repeated words
    - Remove repeated title if present
    - Allow common English abbreviations
    - Provide heuristic detection of predominantly-English summaries
    """

    _ABBREV = re.compile(r"\b(NEET|JEE|AICTE|IIT|NIT|SSC|CBSE|UPSC|IAS|IPS|GPS|COVID-19)\b", re.IGNORECASE)
    _MARKDOWN = re.compile(r"(^|\n)\s*([\-*+]\s+)|[`*_]{1,3}|^#{1,6}\s+", re.MULTILINE)
    _BULLET = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)
    _MULTI_PUNC = re.compile(r"([\u0964\u002E\u3002!?,]){2,}")

    @classmethod
    def clean(cls, summary: Any, title: Optional[str] = None) -> str:
        if summary is None:
            return ""
        s = unicodedata.normalize("NFKC", str(summary))
        s = cls._MARKDOWN.sub(" ", s)
        s = cls._BULLET.sub(" ", s)
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        s = re.sub(r"\s+", " ", s).strip()
        s = cls._MULTI_PUNC.sub(lambda m: m.group(1), s)
        # remove repeated words sequences (simple heuristic)
        words = s.split()
        cleaned_words = []
        last = None
        for w in words:
            if w == last:
                continue
            cleaned_words.append(w)
            last = w
        s = " ".join(cleaned_words)
        # drop title occurrences at start
        if title:
            t = Normalizer.normalize_whitespace(title)
            if t and s.startswith(t):
                s = s[len(t):].strip()
        return s

    @classmethod
    def english_fraction(cls, text: str) -> float:
        if not text:
            return 0.0
        words = re.findall(r"\w+", text)
        if not words:
            return 0.0
        eng = 0
        for w in words:
            # allow known abbreviations
            if cls._ABBREV.search(w):
                continue
            # treat as Telugu if contains Telugu block
            if re.search(r"[\u0C00-\u0C7F]", w):
                continue
            # treat numbers and hyphenated tokens as neutral
            if re.fullmatch(r"[0-9\-]+", w):
                continue
            # basic latin word
            if re.search(r"[A-Za-z]", w):
                eng += 1
        return eng / len(words)

    @classmethod
    def _concisify_phrase(cls, value: str, *, max_words: int) -> str:
        text = Normalizer.normalize_whitespace(value)
        if not text:
            return ""
        words = [word for word in re.split(r"\s+", text) if word]
        if not words:
            return ""
        concise = " ".join(words[:max_words])
        if re.search(r"[A-Za-z]", concise):
            concise = concise.title()
        return concise

    @classmethod
    def normalize_keywords(cls, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        normalized: List[str] = []
        seen = set()
        for item in value:
            text = Normalizer.normalize_whitespace(item)
            if not text:
                continue
            dedupe_key = text.casefold()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(text)
        normalized = sorted(normalized, key=lambda item: item.casefold())
        return normalized[:10]

    @classmethod
    def normalize_people(cls, value: Any) -> List[Dict[str, str]]:
        if not isinstance(value, list):
            return []
        normalized: List[Dict[str, str]] = []
        seen = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            name = Normalizer.normalize_whitespace(item.get("name"))
            designation = Normalizer.normalize_whitespace(item.get("designation"))
            if not name and not designation:
                continue
            dedupe_key = (name.casefold(), designation.casefold())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append({"name": name, "designation": designation})
        return normalized

    @classmethod
    def normalize_entities(cls, value: Any) -> List[Dict[str, str]]:
        if not isinstance(value, list):
            return []
        normalized: List[Dict[str, str]] = []
        seen = set()
        for item in value:
            if not isinstance(item, dict):
                continue
            entity_type = Normalizer.normalize_whitespace(item.get("type"))
            name = Normalizer.normalize_whitespace(item.get("name"))
            normalized_value = Normalizer.normalize_whitespace(item.get("normalized")) or name.casefold()
            if not entity_type or not name:
                continue
            key = (entity_type.casefold(), normalized_value.casefold())
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"type": entity_type, "name": name, "normalized": normalized_value})
        return normalized

    @classmethod
    def normalize_confidence(cls, value: Any) -> float:
        try:
            confidence = float(value)
        except Exception:
            confidence = 0.0
        return round(max(0.0, min(1.0, confidence)), 2)

    @classmethod
    def normalize_title(cls, value: Any) -> str:
        return Normalizer.normalize_whitespace(value)

    @classmethod
    def normalize_json_candidate(cls, value: str) -> str:
        text = unicodedata.normalize("NFKC", value or "")
        text = text.replace("“", '"').replace("”", '"').replace("„", '"')
        text = text.replace("‘", "'").replace("’", "'")
        text = re.sub(r",(?=\s*[}\]])", "", text)
        return text.strip()


class SentimentNormalizer:
    """Convert noisy model labels into the fixed sentiment set."""
    _ALIASES = (
        # Problem-related
        (re.compile(r"\b(problem|issue|complaint|grievance|pothole|road\s*issue|road\s*damage|water\s*problem|water\s*issue|electricity\s*(issue|cut)|drainage|flood|damage|shortage|repair|public\s*issue|పోటు|ఫిర్యాదు|గర్భ)\b", re.IGNORECASE), "Problem"),
        # Negative/crime-related
        (re.compile(r"\b(crime|criminal|murder|theft|fraud|robbery|assault|attack|rape|drug|drugs|corruption|bribe|bribery|violence|accident|death|మరణాలు|హత్య|అత్యాచారం|చోరీ|మోసం)\b", re.IGNORECASE), "Negative"),
        # Positive
        (re.compile(r"\b(positive|appreciation|praise|success|achievement|relief|support|approval|approved|inauguration|launch|felicitation|award|congratulation|good\s*news|award|ప్రశంస|విజయం|అభినందన|వికాసం|సాఫల్య)\b", re.IGNORECASE), "Positive"),
        # Statement / news
        (re.compile(r"\b(news|announcement|meeting|report|event|update|briefing|inspection|press\s*meet|press\s*conference|వార్త|ప్రకటన|సమావేశం|కార్యక్రమం|రిపోర్ట్|ఇన్స్పెక్షన్|స్ధితి|స్టాటస్)\b", re.IGNORECASE), "Statement"),
        # Specific mappings for Telugu terms
        (re.compile(r"\b(వార్త|ప్రకటన|సమావేశం|చెప్పారు|పత్రిక)\b", re.IGNORECASE), "Statement"),
        (re.compile(r"\b(రహదారి|రోడ్|రహదారి సమస్య|రోడ్ ఇష్యూ|రహదారులు)\b", re.IGNORECASE), "Problem"),
        (re.compile(r"\b(అవార్డు|పురస్కారం|ఇనాగ్యురేషన్|ప్రారంభం|ఉద‌్ఘాట‌న)\b", re.IGNORECASE), "Positive"),
    )

    @classmethod
    def normalize(cls, value: Any) -> str:
        text = cls._extract_text(value)
        if not text:
            return "Statement"

        direct = text.casefold()
        if direct in {"problem", "positive", "negative", "statement"}:
            return direct.title()

        for pattern, sentiment in cls._ALIASES:
            if pattern.search(text):
                return sentiment

        return "Statement"

    @staticmethod
    def _extract_text(value: Any) -> str:
        if isinstance(value, dict):
            for key in ("sentiment", "primary", "label", "value"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return Normalizer.normalize_whitespace(candidate)
            return ""
        if value is None:
            return ""
        return Normalizer.normalize_whitespace(value)


class ProblemIDGenerator:
    """Generate deterministic stable problem IDs from normalized semantic fields."""

    _lock = threading.Lock()

    @classmethod
    def generate(cls, normalized_category: str, normalized_district: str, normalized_problem: str) -> str:
        with cls._lock:
            payload = "|".join(
                [
                    cls._sanitize(normalized_category),
                    cls._sanitize(normalized_district),
                    cls._sanitize(normalized_problem),
                ]
            )
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12].upper()
            return f"PROB-{digest}"

    @staticmethod
    def _sanitize(value: Any) -> str:
        text = unicodedata.normalize("NFC", str(value or ""))
        text = text.strip().casefold()
        text = re.sub(r"\s+", " ", text)
        filtered: List[str] = []
        for char in text:
            category = unicodedata.category(char)
            if category.startswith("P") or category.startswith("S") or category == "Cf":
                continue
            filtered.append(char)
        return re.sub(r"\s+", "", "".join(filtered))


class JSONRepairer:
    """Repair common malformed JSON responses before validation."""

    @staticmethod
    def parse(raw_text: str) -> Dict[str, Any]:
        candidates = JSONRepairer._candidate_payloads(raw_text)
        last_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                parsed = _json_loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception as exc:
                last_error = exc
            try:
                literal = ast.literal_eval(candidate)
                if isinstance(literal, dict):
                    return literal
            except Exception as exc:
                last_error = exc
        raise ValueError(f"Unable to parse JSON after repair attempts: {last_error}")

    @staticmethod
    def _candidate_payloads(raw_text: str) -> List[str]:
        text = Normalizer.normalize_json_candidate(raw_text)
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        candidates = [text]
        try:
            candidates.append(_extract_first_json_object(text))
        except Exception:
            pass
        repaired = Normalizer.normalize_json_candidate(text)
        if repaired not in candidates:
            candidates.append(repaired)
        return candidates


class EntityExtractor:
    """Extract deterministic entities from the article text and normalized model output."""

    ENTITY_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
        ("Organization", re.compile(r"(\S+(?:\s+\S+){0,4}(?:కార్యాలయం|యూనియన్|సంఘం|కళాశాల|పాఠశాల|డివిజన్|శాఖ|కమిటీ|విభాగం|పార్టీ|మండలి|సమాఖ్య|సంస్థ))")),
        ("Department", re.compile(r"(\S+(?:\s+\S+){0,3}(?:విభాగం|శాఖ|కార్యాలయం|అధికారులు|సిబ్బంది))")),
        ("Political Party", re.compile(r"(వైసీపీ|టిడిపి|బీజేపీ|కాంగ్రెస్|జనసేన|సీపీఎం|సీపీఐ)")),
        ("Scheme", re.compile(r"(మన బడి[–-]మన భవిష్యత్తు|అమృత్ భారత్ స్టేషన్ పథకం|పీఆర్సీ|ప్రజా సమస్యల పరిష్కార వేదిక)")),
    ]

    def extract(self, article: ArticleInput, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        entities: List[Dict[str, str]] = []
        seen = set()

        def add_entity(entity_type: str, name: str) -> None:
            normalized = self._normalize(name)
            if not normalized:
                return
            key = (entity_type, normalized)
            if key in seen:
                return
            seen.add(key)
            entities.append({"type": entity_type, "name": name.strip(), "normalized": normalized})

        for person in analysis.get("people", []):
            if isinstance(person, dict):
                add_entity("Person", person.get("name", ""))

        location = analysis.get("location", {})
        if isinstance(location, dict):
            for key in ("village", "village_telugu", "mandal", "mandal_telugu", "district", "district_telugu"):
                value = location.get(key)
                if isinstance(value, str) and value.strip():
                    label = "District" if "district" in key else "Mandal" if "mandal" in key else "Village"
                    add_entity(label, value)

        text = f"{article.title}\n{article.content}\n{analysis.get('summary', '')}"
        for entity_type, pattern in self.ENTITY_PATTERNS:
            for match in pattern.findall(text):
                add_entity(entity_type, match)

        for raw_name in self._extract_capitalized_names(text):
            add_entity("Person", raw_name)

        return entities

    @staticmethod
    def _extract_capitalized_names(text: str) -> List[str]:
        candidates = re.findall(r"(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", text)
        return candidates[:20]

    @staticmethod
    def _normalize(value: Any) -> str:
        text = Normalizer.normalize_whitespace(value)
        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"[\s\-–—,.;:!?()\[\]{}'\"“”‘’।,]+", "", text)
        return text.casefold()


class TrendDetector:
    """Cluster related problem articles into deterministic trends."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def build(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        with self._lock:
            clusters: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
            for article in articles:
                if article.get("sentiment") != "Problem":
                    continue
                category = article.get("category", "")
                subcategory = article.get("subcategory", "")
                district = article.get("location", {}).get("district", "")
                clusters[(category, subcategory, district)].append(article)

            trends: List[Dict[str, Any]] = []
            for (category, subcategory, district), bucket in clusters.items():
                trend_groups: List[Dict[str, Any]] = []
                for article in bucket:
                    problem = Normalizer.normalize_whitespace(article.get("problem") or article.get("summary") or "")
                    placed = False
                    for group in trend_groups:
                        if self._is_similar(problem, group["seed_problem"]):
                            self._append_group(group, article)
                            placed = True
                            break
                    if not placed:
                        group = self._new_group(category, subcategory, district, problem, article)
                        trend_groups.append(group)
                for group in trend_groups:
                    trends.append(group)

            trends.sort(key=lambda item: (item["category"], item["subcategory"], item["district"], item["trend_id"]))
            return trends

    @staticmethod
    def _new_group(category: str, subcategory: str, district: str, problem: str, article: Dict[str, Any]) -> Dict[str, Any]:
        trend_id = "TREND-" + hashlib.sha256(f"{category}|{subcategory}|{district}|{problem}".encode("utf-8")).hexdigest()[:8].upper()
        timestamp = article.get("processing", {}).get("timestamp")
        return {
            "trend_id": trend_id,
            "category": category,
            "subcategory": subcategory,
            "district": district,
            "seed_problem": problem,
            "occurrence_count": 1,
            "first_seen": timestamp,
            "last_seen": timestamp,
            "related_problem_ids": [article.get("problem_id")],
        }

    @staticmethod
    def _append_group(group: Dict[str, Any], article: Dict[str, Any]) -> None:
        group["occurrence_count"] += 1
        group["last_seen"] = article.get("processing", {}).get("timestamp")
        problem_id = article.get("problem_id")
        if problem_id and problem_id not in group["related_problem_ids"]:
            group["related_problem_ids"].append(problem_id)

    @staticmethod
    def _is_similar(left: str, right: str) -> bool:
        if not left or not right:
            return False
        if left == right:
            return True
        ratio = SequenceMatcher(None, left, right).ratio()
        return ratio >= 0.78


class StatisticsCollector:
    """Compute master statistics from finalized article records."""

    def build(self, articles: List[Dict[str, Any]], duplicates: List[Dict[str, Any]], failures: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(articles) + len(duplicates) + len(failures)
        success_articles = [article for article in articles if article.get("status") == STATUS_SUCCESS]
        confidences = [float(article.get("confidence", 0.0)) for article in success_articles if isinstance(article.get("confidence"), (int, float))]
        qualities = [float(article.get("quality_score", 0.0)) for article in success_articles if isinstance(article.get("quality_score", 0.0), (int, float))]

        category_counts = Counter(article.get("category") for article in articles if article.get("category"))
        district_counts = Counter(article.get("location", {}).get("district") for article in articles if article.get("location", {}).get("district"))
        authority_counts = Counter(article.get("authority") for article in articles if article.get("authority"))
        problem_counts = Counter(article.get("problem_id") for article in articles if article.get("problem_id"))

        sentiment_counts = Counter(article.get("sentiment") for article in articles if article.get("sentiment"))
        return {
            "success_rate": round((len(success_articles) / total) if total else 0.0, 4),
            "average_processing_time": round(self._avg((article.get("processing", {}).get("processing_time_ms", 0) or 0) / 1000.0 for article in articles), 4),
            "average_confidence": round(self._avg(confidences), 4),
            "average_quality": round(self._avg(qualities), 4),
            "category_counts": dict(category_counts),
            "district_counts": dict(district_counts),
            "authority_counts": dict(authority_counts),
            "problem_counts": dict(problem_counts),
            "duplicate_count": len(duplicates),
            "failure_count": len(failures),
            "sentiment_counts": dict(sentiment_counts),
        }

    @staticmethod
    def _avg(values: Any) -> float:
        values = [float(value) for value in values if value is not None]
        return sum(values) / len(values) if values else 0.0


class PriorityScheduler:
    """Deterministically rank articles so higher-value items are processed first."""

    @staticmethod
    def prioritize(articles: List[ArticleInput]) -> List[ArticleInput]:
        heap: List[Tuple[int, int, ArticleInput]] = []
        for index, article in enumerate(articles):
            score = PriorityScheduler._score(article)
            heapq.heappush(heap, (-score, index, article))
        ordered: List[ArticleInput] = []
        while heap:
            _, _, article = heapq.heappop(heap)
            ordered.append(article)
        return ordered

    @staticmethod
    def _score(article: ArticleInput) -> int:
        score = 0
        score += min(len(article.content) // 100, 20)
        score += 5 if "కేసు" in article.content or "ఫిర్యాదు" in article.content or "వివాద" in article.content else 0
        score += 5 if article.title else 0
        score += 10 if len(article.content) > 300 else 0
        return score


# ===========================================================
# DOMAIN CONSTANTS
# ===========================================================


SYSTEM_PROMPT = (
    "You are an expert Telugu newspaper analyst. Return ONLY valid JSON. Never add markdown, explanations, timestamps, hashes, IDs, or extra text. "
    "Never hallucinate or invent facts. Never rewrite the article. problem_id, trend_id, article_id, and article_hash must always be null. "
    "Sentiment must be exactly one of Problem, Positive, Negative, or Statement. Never return crime, news, report, meeting, announcement, event, వార్త, or any other label. If uncertain, choose Statement. "
    "Summary must always be Telugu, 50-60 words, journalistic, factual, and free of English, numbering, bullets, or markdown. "
    "People must be objects with name and designation. Entities must be objects with type, name, and normalized. "
    "Keywords must be 5-10 unique Telugu-preferred items."
)


USER_PROMPT_TEMPLATE = (
    "Analyze this single OCR article and return the required JSON only.\n"
    "TITLE: {title}\n"
    "CONTENT: {content}\n"
    "Schema: title, sentiment, category, subcategory, problem, problem_id, trend_id, article_id, article_hash, severity, authority, location, people, entities, summary, keywords, confidence. "
    "Do not return legacy type labels, classification, statistics, timestamps, hashes, or IDs except null placeholders for problem_id, trend_id, article_id, and article_hash. "
    "Use sentiment only from Problem, Positive, Negative, Statement. If uncertain, choose Statement."
)

CLASSIFICATION_PROMPT_TEMPLATE = (
    "Analyze this single OCR article and return JSON only.\n"
    "TITLE: {title}\n"
    "CONTENT: {content}\n"
    "Return exactly this shape: {{\"sentiment\":\"\",\"category\":\"\",\"subcategory\":\"\",\"problem\":\"\",\"severity\":\"\",\"authority\":\"\"}}."
)

EXTRACTION_PROMPT_TEMPLATE = (
    "Analyze this single OCR article and return JSON only.\n"
    "TITLE: {title}\n"
    "CONTENT: {content}\n"
    "Return exactly this shape: {{\"location\":{{\"village\":\"\",\"town\":\"\",\"mandal\":\"\",\"district\":\"\",\"state\":\"Andhra Pradesh\"}},\"people\":[],\"entities\":[],\"keywords\":[]}}."
)

SUMMARY_PROMPT_TEMPLATE = (
    "Analyze this single OCR article and return JSON only.\n"
    "TITLE: {title}\n"
    "CONTENT: {content}\n"
    "Return exactly this shape: {{\"summary\":\"\"}}."
)


SEPARATOR_PATTERN = re.compile(r"(?m)^\s*-{20,}\s*$")
TITLE_PATTERN = re.compile(r"(?is)\bTITLE\s*:\s*(.*?)(?:\n\s*CONTENT\s*:\s*|\Z)")
CONTENT_PATTERN = re.compile(r"(?is)\bCONTENT\s*:\s*(.*)\Z")


# ===========================================================
# DATA MODELS
# ===========================================================


@dataclass(slots=True)
class ArticleInput:
    article_id: str
    article_index: int
    raw_text: str
    title: str
    content: str
    source_sha256: str

    @property
    def normalized_identity(self) -> str:
        return self.source_sha256


@dataclass(slots=True)
class ArticleOutcome:
    article_id: str
    article_index: int
    source_sha256: str
    status: str
    analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duplicate_of: Optional[str] = None
    api_key_index: Optional[int] = None
    retry_count: int = 0
    processing_seconds: float = 0.0
    tokens: Optional[Dict[str, Optional[int]]] = None

    def to_record(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "article_index": self.article_index,
            "source_sha256": self.source_sha256,
            "status": self.status,
            "analysis": self.analysis,
            "error": self.error,
            "duplicate_of": self.duplicate_of,
            "api_key_index": self.api_key_index,
            "retry_count": self.retry_count,
            "processing_seconds": round(self.processing_seconds, 3),
            "tokens": self.tokens,
        }


@dataclass(slots=True)
class ParsedAnalysis:
    data: Dict[str, Any]
    tokens: Dict[str, Optional[int]]
    api_key_index: int
    attempts: int


@dataclass(slots=True)
class KeyState:
    key: str
    index: int
    failure_count: int = 0
    available_at: float = 0.0
    last_used: float = 0.0
    success_count: int = 0
    total_requests: int = 0
    total_tokens: int = 0
    latency_total: float = 0.0
    average_latency: float = 0.0
    rate_limit_count: int = 0
    timeout_count: int = 0


@dataclass(slots=True)
class AppConfig:
    input_file: Path = INPUT_FILE
    output_dir: Path = OUTPUT_DIR
    individual_output_dir: Path = INDIVIDUAL_OUTPUT_DIR
    checkpoint_file: Path = CHECKPOINT_FILE
    all_articles_file: Path = ALL_ARTICLES_FILE
    all_articles_csv_file: Path = ALL_ARTICLES_CSV_FILE
    failed_articles_file: Path = FAILED_ARTICLES_FILE
    processing_log_file: Path = PROCESSING_LOG_FILE
    model_name: str = MODEL_NAME
    temperature: float = TEMPERATURE
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    workers: int = DEFAULT_WORKERS
    max_retries: int = MAX_RETRIES
    cooldown_seconds: float = COOLDOWN_SECONDS
    empty_article_min_chars: int = EMPTY_ARTICLE_MIN_CHARS


# ===========================================================
# ARTICLE SPLITTING
# ===========================================================


class ArticleSplitter:
    """Split OCR newspaper text into individual article blocks and parse each block."""

    def split(self, text: str) -> List[ArticleInput]:
        cleaned_text = Normalizer.clean_ocr_text(text)
        blocks = [block.strip() for block in SEPARATOR_PATTERN.split(cleaned_text) if block.strip()]
        articles: List[ArticleInput] = []

        for index, block in enumerate(blocks, start=1):
            article = self._parse_block(block=block, index=index)
            articles.append(article)

        return articles

    def _parse_block(self, block: str, index: int) -> ArticleInput:
        title_match = TITLE_PATTERN.search(block)
        content_match = CONTENT_PATTERN.search(block)

        title = Normalizer.normalize_whitespace(title_match.group(1) if title_match else "")
        content = Normalizer.normalize_whitespace(content_match.group(1) if content_match else "")

        if not title and not content:
            fallback = Normalizer.normalize_whitespace(block)
            title = fallback[:120]
            content = fallback

        raw_text = f"TITLE:\n{title}\n\nCONTENT:\n{content}"
        source_sha256 = _sha256_hex(Normalizer.normalize_whitespace(f"{title}\n{content}"))
        article_id = f"article_{index:06d}"

        return ArticleInput(
            article_id=article_id,
            article_index=index,
            raw_text=raw_text,
            title=title,
            content=content,
            source_sha256=source_sha256,
        )


# ===========================================================
# API KEY MANAGER
# ===========================================================


class APIKeyManager:
    """Thread-safe round-robin API key allocator with cooldowns for API failures only."""

    def __init__(self, keys: Sequence[str], cooldown_seconds: float, logger: Optional[logging.Logger] = None) -> None:
        cleaned_keys = [key.strip() for key in keys if key and key.strip()]
        if not cleaned_keys:
            raise RuntimeError(
                "No Groq API keys found. Set GROQ_API_KEY, GROQ_API_KEYS, or GROQ_API_KEY_1 ... GROQ_API_KEY_N in the environment."
            )

        self._keys: List[KeyState] = [KeyState(key=value, index=position + 1) for position, value in enumerate(cleaned_keys)]
        self._cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._last_assigned_key_index = 1
        self._next_index = 0
        self._logger = logger

    @property
    def last_assigned_key_index(self) -> int:
        with self._lock:
            return self._last_assigned_key_index

    def acquire(self) -> KeyState:
        with self._condition:
            while True:
                now = time.monotonic()
                selected: Optional[KeyState] = None

                for offset in range(len(self._keys)):
                    candidate_index = (self._next_index + offset) % len(self._keys)
                    state = self._keys[candidate_index]
                    if state.available_at <= now:
                        selected = state
                        self._next_index = (candidate_index + 1) % len(self._keys)
                        self._last_assigned_key_index = state.index
                        state.total_requests += 1
                        state.last_used = now
                        state.available_at = now
                        break

                if selected is not None:
                    if self._logger is not None:
                        self._logger.info("Using Key #%s", selected.index)
                    self._condition.notify_all()
                    return selected

                earliest_ready = min(state.available_at for state in self._keys)
                wait_seconds = max(0.1, earliest_ready - now)
                self._condition.wait(timeout=wait_seconds)

    def mark_failure(self, key_index: int, reason: str, *, latency_seconds: float = 0.0) -> None:
        with self._condition:
            state = self._keys[key_index - 1]
            state.failure_count += 1
            lowered = reason.lower()
            is_api_failure = any(token in lowered for token in ("429", "rate limit", "quota", "timeout", "timed out", "connection", "network", "500", "502", "503", "504"))
            if is_api_failure:
                cooldown_seconds = self._cooldown_seconds
                if "429" in lowered or "rate limit" in lowered or "quota" in lowered:
                    cooldown_seconds = max(cooldown_seconds, 15.0)
                elif "timeout" in lowered or "timed out" in lowered:
                    cooldown_seconds = max(cooldown_seconds, 8.0)
                state.available_at = time.monotonic() + cooldown_seconds
                state.rate_limit_count += 1 if ("429" in lowered or "rate limit" in lowered or "quota" in lowered) else 0
                state.timeout_count += 1 if ("timeout" in lowered or "timed out" in lowered) else 0
            state.latency_total += max(0.0, latency_seconds)
            state.average_latency = (state.latency_total / max(1, state.total_requests)) if state.total_requests else 0.0
            if self._logger is not None:
                if is_api_failure:
                    cooldown_seconds = max(self._cooldown_seconds, 15.0) if ("429" in lowered or "rate limit" in lowered or "quota" in lowered) else max(self._cooldown_seconds, 8.0)
                    self._logger.warning("Cooldown Started | key=%s | reason=%s | cooldown=%.2fs", key_index, reason, cooldown_seconds)
                else:
                    self._logger.info("Key Failure | key=%s | reason=%s", key_index, reason)
            self._condition.notify_all()

    def mark_success(self, key_index: int, *, latency_seconds: float = 0.0, tokens: Optional[int] = None) -> None:
        with self._condition:
            state = self._keys[key_index - 1]
            state.success_count += 1
            state.failure_count = 0
            state.available_at = 0.0
            state.latency_total += max(0.0, latency_seconds)
            state.average_latency = (state.latency_total / max(1, state.total_requests)) if state.total_requests else 0.0
            if tokens is not None:
                state.total_tokens += max(0, int(tokens))
            if self._logger is not None:
                self._logger.info("Request Success | key=%s | latency=%.2fs | tokens=%s", key_index, latency_seconds, tokens if tokens is not None else "n/a")
            self._condition.notify_all()

    def get_statistics(self) -> List[Dict[str, Any]]:
        with self._condition:
            stats: List[Dict[str, Any]] = []
            for state in self._keys:
                stats.append({
                    "index": state.index,
                    "requests": state.total_requests,
                    "success": state.success_count,
                    "failures": state.failure_count,
                    "429": state.rate_limit_count,
                    "tokens": state.total_tokens,
                    "average_latency": round(state.average_latency, 3),
                })
            return stats

    def write_statistics_file(self, path: Path) -> None:
        payload = {"keys": self.get_statistics()}
        _atomic_write_json(path, payload, pretty=True)


def _article_log_context(article: ArticleInput, *, worker_id: Optional[str] = None, api_key_index: Optional[int] = None, retry_count: int = 0) -> str:
    parts = [f"article_id={article.article_id}", f"title={article.title or '<untitled>'}"]
    if worker_id:
        parts.append(f"worker={worker_id}")
    if api_key_index is not None:
        parts.append(f"api_key={api_key_index}")
    parts.append(f"retry={retry_count}")
    return " | ".join(parts)


def _discover_api_keys() -> List[str]:
    numbered: List[Tuple[int, str]] = []
    for env_key, env_value in os.environ.items():
        match = re.fullmatch(r"GROQ_API_KEY_(\d+)", env_key)
        if match and env_value.strip():
            numbered.append((int(match.group(1)), env_value.strip()))

    numbered.sort(key=lambda item: item[0])
    discovered = [value for _, value in numbered]

    explicit_list = os.getenv("GROQ_API_KEYS", "").strip()
    if explicit_list:
        for part in re.split(r"[,;\s]+", explicit_list):
            if part.strip():
                discovered.append(part.strip())

    single_key = os.getenv("GROQ_API_KEY", "").strip()
    if single_key:
        discovered.append(single_key)

    unique_keys: List[str] = []
    seen = set()
    for key in discovered:
        if key not in seen:
            unique_keys.append(key)
            seen.add(key)
    return unique_keys


# ===========================================================
# VALIDATION AND NORMALIZATION
# ===========================================================


class AnalysisValidator:
    """Validate, normalize, and finalize model output so only trusted records are accepted."""

    @staticmethod
    def validate_raw(data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("Groq output must be a JSON object")

        for key in ("title", "sentiment", "category", "subcategory", "problem", "summary", "severity", "authority", "article_id", "article_hash", "trend_id", "problem_id"):
            if key in data and data.get(key) is not None and not isinstance(data.get(key), str):
                raise ValueError(f"{key} must be a string or null")
        if "location" in data and data.get("location") is not None and not isinstance(data.get("location"), dict):
            raise ValueError("location must be an object or null")
        if "people" in data and data.get("people") is not None and not isinstance(data.get("people"), list):
            raise ValueError("people must be an array or null")
        if "entities" in data and data.get("entities") is not None and not isinstance(data.get("entities"), list):
            raise ValueError("entities must be an array or null")
        if "keywords" in data and data.get("keywords") is not None and not isinstance(data.get("keywords"), list):
            raise ValueError("keywords must be an array or null")
        if "confidence" in data and data.get("confidence") is not None and not isinstance(data.get("confidence"), (int, float)):
            raise ValueError("confidence must be numeric or null")

    @staticmethod
    def normalize(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(raw_data)
        data["title"] = Normalizer.normalize_title(data.get("title", ""))
        data["sentiment"] = SentimentNormalizer.normalize(data.get("sentiment"))
        data["category"] = Normalizer.normalize_category(data.get("category"))
        data["subcategory"] = Normalizer.normalize_subcategory(data.get("subcategory") or data.get("problem") or data.get("category"))
        data["problem"] = Normalizer.normalize_problem(data.get("problem")) if data["sentiment"] == "Problem" else None
        data["problem_id"] = None
        data["severity"] = Normalizer.normalize_whitespace(data.get("severity", ""))
        data["authority"] = Normalizer.normalize_whitespace(data.get("authority", ""))
        data["location"] = Normalizer.normalize_location(data.get("location", {}))
        data["people"] = Normalizer.normalize_people(data.get("people", []))
        data["entities"] = Normalizer.normalize_entities(data.get("entities", []))
        data["keywords"] = Normalizer.normalize_keywords(data.get("keywords", []))
        # run the summary through a dedicated cleaner that preserves Telugu
        data["summary"] = SummaryNormalizer.clean(data.get("summary", ""), title=data.get("title", ""))
        data["confidence"] = Normalizer.normalize_confidence(data.get("confidence"))
        return data

    @staticmethod
    def validate_final(data: Dict[str, Any]) -> None:
        AnalysisValidator._validate_common_shape(data)

        if data["sentiment"] not in ALLOWED_SENTIMENTS:
            raise ValueError(f"Invalid sentiment: {data['sentiment']}")
        if not AnalysisValidator._is_valid_category(data["category"]):
            raise ValueError(f"Invalid category: {data['category']}")
        if not AnalysisValidator._is_valid_subcategory(data["subcategory"]):
            raise ValueError(f"Invalid subcategory: {data['subcategory']}")

        location = data["location"]
        if not isinstance(location, dict):
            raise ValueError("location must be an object")
        expected_location_keys = {
            "village_telugu",
            "village",
            "town_telugu",
            "town",
            "mandal_telugu",
            "mandal",
            "district_telugu",
            "district",
            "state_telugu",
            "state",
        }
        if expected_location_keys.difference(location.keys()):
            raise ValueError("location object is incomplete")
        if location.get("state") != "Andhra Pradesh":
            raise ValueError("location.state must be Andhra Pradesh")

        if not isinstance(data["people"], list):
            raise ValueError("people must be an array")
        if not isinstance(data["entities"], list):
            raise ValueError("entities must be an array")
        if not isinstance(data["keywords"], list):
            raise ValueError("keywords must be an array")

        if data["sentiment"] == "Problem":
            if not data["problem"]:
                raise ValueError("problem is required for Problem articles")
            if not data["problem_id"]:
                raise ValueError("problem_id is required for Problem articles")
        else:
            if data["problem"] is not None:
                raise ValueError("problem must be null when sentiment is not Problem")
            if data["problem_id"] is not None:
                raise ValueError("problem_id must be null when sentiment is not Problem")

        AnalysisValidator._validate_summary(data["summary"])
        AnalysisValidator._validate_keywords(data["keywords"])
        AnalysisValidator._validate_people(data["people"])
        AnalysisValidator._validate_entities(data["entities"])
        AnalysisValidator._validate_confidence(data["confidence"])
        AnalysisValidator._validate_processing(data["processing"])
        AnalysisValidator._validate_quality_score(data["quality_score"])

    @staticmethod
    def _validate_common_shape(data: Dict[str, Any]) -> None:
        required_keys = {
            "title",
            "sentiment",
            "category",
            "subcategory",
            "problem",
            "problem_id",
            "trend_id",
            "article_id",
            "article_hash",
            "severity",
            "authority",
            "location",
            "people",
            "entities",
            "summary",
            "keywords",
            "confidence",
            "processing",
            "quality_score",
        }
        missing = required_keys.difference(data.keys())
        if missing:
            raise ValueError(f"Missing required keys: {sorted(missing)}")

        if not isinstance(data.get("title"), str) or not data["title"].strip():
            raise ValueError("title must be a non-empty string")
        if not isinstance(data.get("sentiment"), str):
            raise ValueError("sentiment must be a string")
        if not isinstance(data.get("category"), str):
            raise ValueError("category must be a string")
        if not isinstance(data.get("subcategory"), str):
            raise ValueError("subcategory must be a string")
        if not isinstance(data.get("summary"), str) or not data["summary"].strip():
            raise ValueError("summary must be a non-empty string")
        if not isinstance(data.get("processing"), dict):
            raise ValueError("processing must be an object")
        if not isinstance(data.get("entities"), list):
            raise ValueError("entities must be an array")
        if not isinstance(data.get("quality_score"), (int, float)):
            raise ValueError("quality_score must be numeric")

    @staticmethod
    def _validate_summary(summary: str) -> None:
        summary_text = Normalizer.normalize_summary(summary)
        # allow summaries with some English abbreviations but detect predominant English
        # Accept 45-65 words (inclusive)
        words = _word_count(summary_text)
        if words < 45 or words > 65:
            raise ValueError(f"summary must contain 45-65 words, found {words}")

        # allow occasional English tokens/abbrev; reject only if >20% English words
        eng_frac = SummaryNormalizer.english_fraction(summary_text)
        if eng_frac > 0.20:
            raise ValueError(f"summary appears predominantly English (fraction={eng_frac:.2f})")

        # ensure at least some Telugu characters are present
        if not re.search(r"[\u0C00-\u0C7F]", summary_text):
            raise ValueError("summary must contain Telugu script characters")

        # minimal grammar/quality checks (heuristic)
        # No repeated sentences or repeated title
        s_lower = re.sub(r"\s+", " ", summary_text.strip())
        if len(s_lower) > 0:
            # repeated sentence heuristic
            sentences = re.split(r'[\.|\!|\?|।]\s*', s_lower)
            trimmed = [s.strip() for s in sentences if s.strip()]
            if len(trimmed) != len(set(trimmed)):
                raise ValueError("summary contains repeated sentences")
            # repeated title
            title = Normalizer.normalize_whitespace(summary_text)
            if title and title == Normalizer.normalize_whitespace(summary_text[: len(title)]):
                pass

    @staticmethod
    def _validate_keywords(keywords: List[str]) -> None:
        if len(keywords) < 5 or len(keywords) > 10:
            raise ValueError(f"keywords must contain 5-10 items, found {len(keywords)}")
        if len({item.casefold() for item in keywords}) != len(keywords):
            raise ValueError("keywords must not contain duplicates")

    @staticmethod
    def _validate_people(people: List[Dict[str, str]]) -> None:
        for item in people:
            if not isinstance(item, dict):
                raise ValueError("people must contain objects")
            if set(item.keys()) != {"name", "designation"}:
                raise ValueError("each people item must contain name and designation")
            if not isinstance(item.get("name"), str) or not isinstance(item.get("designation"), str):
                raise ValueError("people name and designation must be strings")

    @staticmethod
    def _validate_entities(entities: List[Dict[str, str]]) -> None:
        for item in entities:
            if not isinstance(item, dict):
                raise ValueError("entities must contain objects")
            if set(item.keys()) != {"type", "name", "normalized"}:
                raise ValueError("each entity must contain type, name, and normalized")
            if not all(isinstance(item.get(key), str) for key in ("type", "name", "normalized")):
                raise ValueError("entity values must be strings")

    @staticmethod
    def _validate_confidence(confidence: Any) -> None:
        if not isinstance(confidence, (int, float)):
            raise ValueError("confidence must be numeric")
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @staticmethod
    def _validate_processing(processing: Dict[str, Any]) -> None:
        required = {"model", "processing_time_ms", "retry_count", "api_key_index", "timestamp"}
        if required.difference(processing.keys()):
            raise ValueError("processing object is incomplete")
        if not isinstance(processing.get("model"), str):
            raise ValueError("processing.model must be a string")
        if not isinstance(processing.get("processing_time_ms"), int):
            raise ValueError("processing.processing_time_ms must be an integer")
        if not isinstance(processing.get("retry_count"), int):
            raise ValueError("processing.retry_count must be an integer")
        if processing.get("api_key_index") is not None and not isinstance(processing.get("api_key_index"), int):
            raise ValueError("processing.api_key_index must be an integer or null")
        if not isinstance(processing.get("timestamp"), str):
            raise ValueError("processing.timestamp must be a string")

    @staticmethod
    def _validate_quality_score(quality_score: Any) -> None:
        if not isinstance(quality_score, (int, float)):
            raise ValueError("quality_score must be numeric")
        if quality_score < 0 or quality_score > 100:
            raise ValueError("quality_score must be between 0 and 100")

    @staticmethod
    def _is_valid_category(category: str) -> bool:
        text = Normalizer.normalize_whitespace(category)
        if not text:
            return False
        if text in ALLOWED_CATEGORIES:
            return True
        return _word_count(text) <= 2

    @staticmethod
    def _is_valid_subcategory(subcategory: str) -> bool:
        text = Normalizer.normalize_whitespace(subcategory)
        return bool(text) and _word_count(text) <= 2


# ===========================================================
# GROQ CLIENT WRAPPER
# ===========================================================


class GroqAnalyzer:
    """Analyze one article with Groq using three independent stages and a single merge step."""

    def __init__(self, config: AppConfig, key_manager: APIKeyManager, logger: logging.Logger) -> None:
        self._config = config
        self._key_manager = key_manager
        self._logger = logger
        self._groq_client_cls = self._load_groq_client_cls()

    @staticmethod
    def _load_groq_client_cls():
        try:
            from groq import Groq  # type: ignore
        except Exception as exc:  # pragma: no cover - runtime dependency check
            raise RuntimeError(
                "The groq package is required. Install it before running this application."
            ) from exc
        return Groq

    def analyze(self, article: ArticleInput) -> ParsedAnalysis:
        last_error: Optional[str] = None
        worker_name = threading.current_thread().name

        self._logger.info("START Groq multi-stage analysis | %s", _article_log_context(article, worker_id=worker_name))

        try:
            started = time.monotonic()
            stage1 = self._run_stage_with_retries(article, stage_name="classification", prompt_template=CLASSIFICATION_PROMPT_TEMPLATE)
            stage2 = self._run_stage_with_retries(article, stage_name="extraction", prompt_template=EXTRACTION_PROMPT_TEMPLATE)
            stage3 = self._run_stage_with_retries(article, stage_name="summary", prompt_template=SUMMARY_PROMPT_TEMPLATE)
            merged = self._merge_stage_payloads(stage1, stage2, stage3, article)
            tokens = self._merge_tokens(stage1["tokens"], stage2["tokens"], stage3["tokens"])
            elapsed = time.monotonic() - started
            total_tokens = tokens.get("total_tokens")

            self._logger.info(
                "SUCCESS Groq multi-stage analysis in %.3fs | %s | tokens=%s",
                elapsed,
                _article_log_context(article, worker_id=worker_name),
                tokens,
            )
            return ParsedAnalysis(data=merged, tokens=tokens, api_key_index=stage3.get("api_key_index", 0), attempts=stage3.get("attempts", 1))

        except Exception as exc:
            error_text = self._format_exception(exc)
            last_error = error_text
            self._logger.warning("FAILURE Groq multi-stage analysis | %s | %s", error_text, _article_log_context(article, worker_id=worker_name))
            raise RuntimeError(last_error or "Groq multi-stage analysis failed without a specific error message") from exc

    @staticmethod
    def _evaluate_summary_stage_output(summary_text: str, *, title: str) -> Tuple[str, int]:
        summary = SummaryNormalizer.clean(summary_text, title=title)
        words = _word_count(summary)
        if not summary:
            return "", 0
        if 50 <= words <= 60:
            return summary, words
        if 45 <= words <= 65:
            return summary, words
        return summary, words

    def _run_stage_with_retries(self, article: ArticleInput, *, stage_name: str, prompt_template: str) -> Dict[str, Any]:
        last_error: Optional[str] = None
        worker_name = threading.current_thread().name
        for attempt in range(1, self._config.max_retries + 1):
            key_state = self._key_manager.acquire()
            client = self._groq_client_cls(api_key=key_state.key)
            try:
                started = time.monotonic()
                response = client.chat.completions.create(
                    model=self._config.model_name,
                    temperature=self._config.temperature,
                    timeout=self._config.request_timeout_seconds,
                    messages=self._build_messages(article, prompt_template=prompt_template, stage_name=stage_name),
                )
                content = self._extract_content(response)
                parsed = self._validate_model_output(content)
                tokens = self._extract_tokens(response)
                elapsed = time.monotonic() - started
                self._key_manager.mark_success(key_state.index, latency_seconds=elapsed, tokens=tokens.get("total_tokens"))

                if stage_name == "summary":
                    summary, words = self._evaluate_summary_stage_output(parsed.get("summary", ""), title=article.title)
                    if not summary:
                        raise ValueError("Summary stage returned empty summary")
                    if words < 45 or words > 65:
                        self._logger.warning(
                            "SUMMARY LENGTH OUTSIDE IDEAL BAND | article=%s | words=%s | title=%s",
                            _article_log_context(article, worker_id=threading.current_thread().name),
                            words,
                            article.title,
                        )

                return {
                    "data": parsed,
                    "tokens": tokens,
                    "api_key_index": key_state.index,
                    "attempts": attempt,
                }
            except Exception as exc:
                elapsed = time.monotonic() - started if "started" in locals() else 0.0
                error_text = self._format_exception(exc)
                last_error = error_text
                if isinstance(exc, (ValueError, json.JSONDecodeError)) and stage_name != "summary":
                    self._logger.warning(
                        "NON-RETRYABLE %s stage error after %.3fs | %s | key=%s | attempt=%s/%s | %s",
                        stage_name,
                        elapsed,
                        _article_log_context(article, worker_id=worker_name, api_key_index=key_state.index, retry_count=attempt),
                        key_state.index,
                        attempt,
                        self._config.max_retries,
                        error_text,
                    )
                    raise
                if self._is_retryable_exception(exc) or stage_name == "summary":
                    self._key_manager.mark_failure(key_state.index, error_text, latency_seconds=elapsed)
                    self._logger.warning(
                        "RETRY %s stage after %.3fs | %s | key=%s | attempt=%s/%s | %s",
                        stage_name,
                        elapsed,
                        _article_log_context(article, worker_id=worker_name, api_key_index=key_state.index, retry_count=attempt),
                        key_state.index,
                        attempt,
                        self._config.max_retries,
                        error_text,
                    )
                    if attempt < self._config.max_retries:
                        continue
                self._key_manager.mark_failure(key_state.index, error_text, latency_seconds=elapsed)
                raise RuntimeError(error_text) from exc
        raise RuntimeError(last_error or f"{stage_name} stage failed without a specific error message")

    def _build_messages(self, article: ArticleInput, *, prompt_template: str, stage_name: str) -> List[Dict[str, str]]:
        user_prompt = prompt_template.format(title=article.title, content=article.content)
        system_prompt = f"You are the {stage_name} engine for Telugu news analysis. Return ONLY valid JSON."
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _extract_content(self, response: Any) -> str:
        try:
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise ValueError("Groq response contains no choices")
            message = choices[0].message
            content = getattr(message, "content", None)
            if isinstance(content, list):
                content = "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Groq response message content is empty")
            return content.strip()
        except Exception as exc:
            raise ValueError(f"Unable to extract Groq message content: {exc}") from exc

    def _validate_model_output(self, raw_content: str) -> Dict[str, Any]:
        return JSONRepairer.parse(raw_content)

    @staticmethod
    def _merge_stage_payloads(stage1: Dict[str, Any], stage2: Dict[str, Any], stage3: Dict[str, Any], article: ArticleInput) -> Dict[str, Any]:
        stage1_data = stage1.get("data") if isinstance(stage1, dict) and "data" in stage1 else stage1 or {}
        stage2_data = stage2.get("data") if isinstance(stage2, dict) and "data" in stage2 else stage2 or {}
        stage3_data = stage3.get("data") if isinstance(stage3, dict) and "data" in stage3 else stage3 or {}

        summary_text = stage3_data.get("summary", "")
        summary, _ = GroqAnalyzer._evaluate_summary_stage_output(summary_text, title=article.title)
        merged = {
            "title": Normalizer.normalize_title(article.title),
            "sentiment": SentimentNormalizer.normalize(stage1_data.get("sentiment")),
            "category": Normalizer.normalize_category(stage1_data.get("category")),
            "subcategory": Normalizer.normalize_subcategory(stage1_data.get("subcategory") or stage1_data.get("category")),
            "problem": Normalizer.normalize_problem(stage1_data.get("problem")) if SentimentNormalizer.normalize(stage1_data.get("sentiment")) == "Problem" else None,
            "problem_id": None,
            "trend_id": None,
            "article_id": None,
            "article_hash": None,
            "severity": Normalizer.normalize_whitespace(stage1_data.get("severity", "")),
            "authority": Normalizer.normalize_whitespace(stage1_data.get("authority", "")),
            "location": Normalizer.normalize_location(stage2_data.get("location", {})),
            "people": Normalizer.normalize_people(stage2_data.get("people", [])),
            "entities": Normalizer.normalize_entities(stage2_data.get("entities", [])),
            "summary": summary,
            "keywords": Normalizer.normalize_keywords(stage2_data.get("keywords", [])),
            "confidence": Normalizer.normalize_confidence(stage1_data.get("confidence", 0.0)),
            "processing": {},
            "quality_score": 0,
        }
        return merged

    @staticmethod
    def _merge_tokens(*token_sets: Dict[str, Optional[int]]) -> Dict[str, Optional[int]]:
        totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for token_set in token_sets:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = token_set.get(key)
                if isinstance(value, int):
                    totals[key] += value
        return totals

    def _extract_tokens(self, response: Any) -> Dict[str, Optional[int]]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    def _is_retryable_exception(self, exc: Exception) -> bool:
        message = self._format_exception(exc).lower()
        retryable_terms = [
            "429",
            "rate limit",
            "quota",
            "timeout",
            "timed out",
            "network",
            "connection",
            "unavailable",
            "service unavailable",
            "temporarily",
            "server error",
            "502",
            "503",
            "504",
        ]
        return any(term in message for term in retryable_terms)

    @staticmethod
    def _format_exception(exc: Exception) -> str:
        return f"{exc.__class__.__name__}: {exc}".strip()


# ===========================================================
# VALIDATION, QUALITY ASSESSMENT, AND DECISION ENGINES
# ===========================================================


class ValidationEngine:
    """Run field-level validation rules and attempt safe, deterministic repairs.

    Each rule returns a dict with keys: severity, field, message, repaired,
    continue_processing.
    """

    @staticmethod
    def _result(severity: str, field: str, message: str, repaired: bool, continue_processing: bool) -> Dict[str, Any]:
        return {
            "severity": severity,
            "field": field,
            "message": message,
            "repaired": repaired,
            "continue_processing": continue_processing,
        }

    @staticmethod
    def run(analysis: Dict[str, Any], repair_log: List[Dict[str, Any]], logger: logging.Logger) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        # CRITICAL checks
        if not analysis.get("title"):
            results.append(ValidationEngine._result("CRITICAL", "title", "Missing title", False, False))
            return results

        if not analysis.get("summary"):
            results.append(ValidationEngine._result("CRITICAL", "summary", "Missing summary", False, False))
            return results

        if not analysis.get("sentiment"):
            results.append(ValidationEngine._result("CRITICAL", "sentiment", "Missing sentiment", False, False))
            return results

        # ERROR checks: try deterministic repairs
        # Sentiment
        sent = analysis.get("sentiment")
        if sent and sent not in ALLOWED_SENTIMENTS:
            orig = sent
            try:
                fixed = SentimentNormalizer.normalize(sent)
            except Exception:
                fixed = None

            if fixed and fixed in ALLOWED_SENTIMENTS:
                analysis["sentiment"] = fixed
                repair_log.append({"field": "sentiment", "original": orig, "repaired": fixed, "type": "normalize_sentiment", "timestamp": _current_timestamp()})
                results.append(ValidationEngine._result("INFO", "sentiment", f"Normalized sentiment {orig} -> {fixed}", True, True))
            else:
                results.append(ValidationEngine._result("ERROR", "sentiment", f"Unknown sentiment: {orig}", False, False))

        # Category
        cat = analysis.get("category")
        if cat and cat not in ALLOWED_CATEGORIES:
            orig = cat
            # map common aliases to Other to avoid failing on 'News'/'వార్త' etc.
            if isinstance(cat, str) and cat.strip().lower() in {"news", "వార్త", "announcement", "meeting"}:
                fixed = "Other"
            else:
                try:
                    fixed = Normalizer.normalize_category(cat)
                except Exception:
                    fixed = None

            if fixed and fixed in ALLOWED_CATEGORIES:
                analysis["category"] = fixed
                repair_log.append({"field": "category", "original": orig, "repaired": fixed, "type": "fuzzy_category", "timestamp": _current_timestamp()})
                results.append(ValidationEngine._result("INFO", "category", f"Normalized category {orig} -> {fixed}", True, True))
            else:
                results.append(ValidationEngine._result("ERROR", "category", f"Unknown category: {orig}", False, False))

        # People list
        people = analysis.get("people")
        if people is None:
            results.append(ValidationEngine._result("WARNING", "people", "Missing people list", False, True))
        else:
            repaired = False
            if isinstance(people, str):
                try:
                    parsed = _json_loads(people)
                    if isinstance(parsed, list):
                        analysis["people"] = parsed
                        repair_log.append({"field": "people", "original": people, "repaired": parsed, "type": "json_parse", "timestamp": _current_timestamp()})
                        repaired = True
                except Exception:
                    repaired = False
            elif isinstance(people, list):
                # Ensure items have 'name'
                new_people = []
                changed = False
                for p in people:
                    if isinstance(p, str):
                        new_people.append({"name": p})
                        changed = True
                    elif isinstance(p, dict) and p.get("name"):
                        new_people.append(p)
                    else:
                        # skip malformed entries
                        changed = True
                if changed:
                    analysis["people"] = new_people
                    repair_log.append({"field": "people", "original": people, "repaired": new_people, "type": "coerce_people", "timestamp": _current_timestamp()})
                    repaired = True

            if repaired:
                results.append(ValidationEngine._result("INFO", "people", "Repaired people list", True, True))

        # Entities list
        entities = analysis.get("entities")
        if entities is None:
            results.append(ValidationEngine._result("WARNING", "entities", "Missing entities list", False, True))
        else:
            repaired = False
            if isinstance(entities, str):
                try:
                    parsed = _json_loads(entities)
                    if isinstance(parsed, list):
                        analysis["entities"] = parsed
                        repair_log.append({"field": "entities", "original": entities, "repaired": parsed, "type": "json_parse", "timestamp": _current_timestamp()})
                        repaired = True
                except Exception:
                    repaired = False
            if repaired:
                results.append(ValidationEngine._result("INFO", "entities", "Repaired entities list", True, True))

        # WARNING-level checks
        # Summary length and English fraction should be downgraded to WARNING
        try:
            summary_text = Normalizer.normalize_summary(analysis.get("summary", ""))
            words = _word_count(summary_text)
            if words < 45 or words > 65:
                results.append(ValidationEngine._result("WARNING", "summary", f"Summary length {words} outside preferred 45-65", False, True))
        except Exception:
            results.append(ValidationEngine._result("WARNING", "summary", "Unable to assess summary length", False, True))

        try:
            eng_frac = SummaryNormalizer.english_fraction(analysis.get("summary", ""))
            if eng_frac > 0.20:
                results.append(ValidationEngine._result("WARNING", "summary", f"English fraction {eng_frac:.2f} > 0.20", False, True))
        except Exception:
            pass

        # Confidence
        conf = analysis.get("confidence")
        if isinstance(conf, (int, float)) and conf < 0.5:
            results.append(ValidationEngine._result("WARNING", "confidence", f"Low confidence: {conf}", False, True))

        return results


class QualityAssessmentEngine:
    """Compute a 0-100 quality score without any LLM involvement."""

    @staticmethod
    def compute(analysis: Dict[str, Any], repair_count: int) -> int:
        score = 0.0
        # summary presence and length
        summary = analysis.get("summary", "") or ""
        words = _word_count(summary)
        if 50 <= words <= 60:
            score += 0.35
        elif 45 <= words <= 65:
            score += 0.25
        else:
            score += max(0.0, min(0.2, words / 100.0))

        # entities & people
        score += 0.2 if analysis.get("entities") else 0.0
        score += 0.15 if analysis.get("people") else 0.0

        # location
        loc = analysis.get("location") or {}
        score += 0.1 if loc.get("district") else 0.0

        # confidence
        conf = analysis.get("confidence")
        if isinstance(conf, (int, float)):
            score += min(0.2, max(0.0, (conf - 0.5) * 0.4))

        # repair penalty
        score -= min(0.15, 0.05 * repair_count)

        final = int(round(max(0.0, min(1.0, score)) * 100))
        return final


class DecisionEngine:
    """Decide whether to accept, retry, or reject based on validation results."""

    @staticmethod
    def decide(results: List[Dict[str, Any]], retries_remaining: int) -> str:
        # If any CRITICAL -> reject
        for r in results:
            if r.get("severity") == "CRITICAL":
                return "reject"

        # If any ERROR not repaired -> retry if allowed, else reject
        has_error_unrepaired = any(r.get("severity") == "ERROR" and not r.get("repaired") for r in results)
        if has_error_unrepaired:
            return "retry" if retries_remaining > 0 else "reject"

        # Otherwise accept (warnings/info do not block)
        return "accept"


# Semantic resolvers and rule-based classifiers have been removed.
# Per the LLM-first architecture, Groq is the sole semantic intelligence engine.
# Python will no longer perform keyword-based category/sentiment inference.
# Previous classes were intentionally deleted to avoid accidental use.


# ===========================================================
# CHECKPOINTING AND OUTPUT MANAGEMENT
# ===========================================================


class CheckpointManager:
    """Persist and restore progress so the application can resume after interruption."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self.state: Dict[str, Any] = {
            "run_id": RUN_ID,
            "processed_article_ids": [],
            "processed_hashes": [],
            "completed_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "duplicate_count": 0,
            "timestamp": _current_timestamp(),
        }
        self.load()

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            loaded = _json_loads(self._path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.state.update(loaded)
        except Exception:
            return

    def save(self) -> None:
        with self._lock:
            self.state["timestamp"] = _current_timestamp()
            _atomic_write_json(self._path, self.state, pretty=True)

    def mark_processed(self, article: ArticleOutcome) -> None:
        with self._lock:
            processed_ids = set(self.state.get("processed_article_ids", []))
            processed_hashes = set(self.state.get("processed_hashes", []))
            processed_ids.add(article.article_id)
            processed_hashes.add(article.source_sha256)
            self.state["processed_article_ids"] = sorted(processed_ids)
            self.state["processed_hashes"] = sorted(processed_hashes)
            self.state["completed_count"] = int(self.state.get("completed_count", 0)) + 1
            if article.status == STATUS_SUCCESS:
                self.state["success_count"] = int(self.state.get("success_count", 0)) + 1
            elif article.status == STATUS_DUPLICATE:
                self.state["duplicate_count"] = int(self.state.get("duplicate_count", 0)) + 1
            else:
                self.state["failed_count"] = int(self.state.get("failed_count", 0)) + 1
            self.state["timestamp"] = _current_timestamp()

    def is_processed(self, article: ArticleInput) -> bool:
        processed_ids = set(self.state.get("processed_article_ids", []))
        processed_hashes = set(self.state.get("processed_hashes", []))
        return article.article_id in processed_ids or article.source_sha256 in processed_hashes

    def snapshot_counts(self) -> Dict[str, int]:
        return {
            "completed": int(self.state.get("completed_count", 0)),
            "success": int(self.state.get("success_count", 0)),
            "failed": int(self.state.get("failed_count", 0)),
            "duplicate": int(self.state.get("duplicate_count", 0)),
        }


class OutputManager:
    """Write article outputs incrementally in JSON and CSV formats."""

    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        self._config = config
        self._logger = logger
        self._lock = threading.Lock()
        self._articles_by_index: Dict[int, Dict[str, Any]] = {}
        self._failed_records: List[Dict[str, Any]] = []
        self._duplicate_records: List[Dict[str, Any]] = []
        self._load_existing_outputs()

    def _load_existing_outputs(self) -> None:
        if self._config.all_articles_file.exists():
            try:
                data = _json_loads(self._config.all_articles_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("articles"), list):
                    for record in data["articles"]:
                        if isinstance(record, dict) and isinstance(record.get("article_index"), int):
                            self._articles_by_index[record["article_index"]] = record
                elif isinstance(data, list):
                    for record in data:
                        if isinstance(record, dict) and isinstance(record.get("article_index"), int):
                            self._articles_by_index[record["article_index"]] = record
            except Exception:
                self._logger.warning("Could not load existing all_articles.json. It will be regenerated.")

        articles_dir = self._config.output_dir / "articles"
        if articles_dir.exists():
            for file_path in sorted(articles_dir.glob("article_*.json")):
                try:
                    payload = _json_loads(file_path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict) and isinstance(payload.get("article_index"), int):
                        self._articles_by_index[payload["article_index"]] = payload
                except Exception:
                    continue

        if self._config.failed_articles_file.exists():
            try:
                data = _json_loads(self._config.failed_articles_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._failed_records = [record for record in data if isinstance(record, dict)]
            except Exception:
                self._logger.warning("Could not load existing failed_articles.json. It will be regenerated.")

        duplicate_file = self._config.output_dir / "duplicate_articles.json"
        if duplicate_file.exists():
            try:
                data = _json_loads(duplicate_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._duplicate_records = [record for record in data if isinstance(record, dict)]
            except Exception:
                self._logger.warning("Could not load existing duplicate_articles.json. It will be regenerated.")

    def write_record(self, outcome: ArticleOutcome) -> None:
        record = outcome.to_record()
        record["updated_at"] = _current_timestamp()

        with self._lock:
            self._store_outcome_locked(outcome, record)

            self._write_auxiliary_outputs_locked()

    def _store_outcome_locked(self, outcome: ArticleOutcome, record: Dict[str, Any]) -> None:
        if outcome.status == STATUS_SUCCESS and isinstance(outcome.analysis, dict):
            article_record = dict(outcome.analysis)
            article_record["status"] = outcome.status
            article_record["source_sha256"] = outcome.source_sha256
            article_record["tokens"] = outcome.tokens or {}
            article_record["updated_at"] = record["updated_at"]
            self._articles_by_index[outcome.article_index] = article_record
            self._write_article_file(article_record)
            return

        if outcome.status == STATUS_DUPLICATE:
            self._duplicate_records = [r for r in self._duplicate_records if r.get("article_id") != outcome.article_id]
            self._duplicate_records.append(record)
            return

        self._failed_records = [r for r in self._failed_records if r.get("article_id") != outcome.article_id]
        self._failed_records.append(record)

    def _write_article_file(self, article_record: Dict[str, Any]) -> None:
        # Keep the in-memory index only; the production output layout does not include
        # per-article JSON files.
        return

    def _write_auxiliary_outputs_locked(self) -> None:
        _atomic_write_json(self._config.failed_articles_file, self._failed_records, pretty=True)
        _atomic_write_json(self._config.output_dir / "duplicate_articles.json", self._duplicate_records, pretty=True)
        self._write_csv_locked(list(self._articles_by_index.values()))

    def _write_csv_locked(self, records: List[Dict[str, Any]]) -> None:
        self._config.output_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self._config.all_articles_csv_file.with_suffix(self._config.all_articles_csv_file.suffix + f".{RUN_ID}.tmp")
        fieldnames = [
            "article_id",
            "article_index",
            "status",
            "title",
            "title_hash",
            "article_hash",
            "sentiment",
            "category",
            "subcategory",
            "problem",
            "problem_id",
            "trend_id",
            "severity",
            "authority",
            "village",
            "village_telugu",
            "town",
            "town_telugu",
            "mandal",
            "mandal_telugu",
            "district",
            "district_telugu",
            "state",
            "state_telugu",
            "people",
            "entities",
            "summary",
            "keywords",
            "confidence",
            "quality_score",
            "source_sha256",
            "error",
            "duplicate_of",
            "api_key_index",
            "retry_count",
            "processing_seconds",
            "processing_model",
            "processing_time_ms",
            "processing_retry_count",
            "processing_api_key_index",
            "processing_timestamp",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        ]

        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                analysis = record
                location = analysis.get("location") or {}
                processing = analysis.get("processing") or {}
                tokens = analysis.get("tokens") or {}
                writer.writerow(
                    {
                        "article_id": analysis.get("article_id"),
                        "article_index": analysis.get("article_index"),
                        "status": analysis.get("status", STATUS_SUCCESS),
                        "title": analysis.get("title"),
                        "title_hash": analysis.get("title_hash"),
                        "article_hash": analysis.get("article_hash"),
                        "sentiment": analysis.get("sentiment"),
                        "category": analysis.get("category"),
                        "subcategory": analysis.get("subcategory"),
                        "problem": analysis.get("problem"),
                        "problem_id": analysis.get("problem_id"),
                        "trend_id": analysis.get("trend_id"),
                        "severity": analysis.get("severity"),
                        "authority": analysis.get("authority"),
                        "village": location.get("village"),
                        "village_telugu": location.get("village_telugu"),
                        "town": location.get("town"),
                        "town_telugu": location.get("town_telugu"),
                        "mandal": location.get("mandal"),
                        "mandal_telugu": location.get("mandal_telugu"),
                        "district": location.get("district"),
                        "district_telugu": location.get("district_telugu"),
                        "state": location.get("state"),
                        "state_telugu": location.get("state_telugu"),
                        "people": _json_dumps(analysis.get("people", []), pretty=False) if analysis else "[]",
                        "entities": _json_dumps(analysis.get("entities", []), pretty=False) if analysis else "[]",
                        "summary": analysis.get("summary"),
                        "keywords": _json_dumps(analysis.get("keywords", []), pretty=False) if analysis else "[]",
                        "confidence": analysis.get("confidence"),
                        "quality_score": analysis.get("quality_score"),
                        "source_sha256": record.get("source_sha256"),
                        "error": record.get("error"),
                        "duplicate_of": record.get("duplicate_of"),
                        "api_key_index": record.get("api_key_index"),
                        "retry_count": record.get("retry_count"),
                        "processing_seconds": record.get("processing_seconds"),
                        "processing_model": processing.get("model"),
                        "processing_time_ms": processing.get("processing_time_ms"),
                        "processing_retry_count": processing.get("retry_count"),
                        "processing_api_key_index": processing.get("api_key_index"),
                        "processing_timestamp": processing.get("timestamp"),
                        "prompt_tokens": tokens.get("prompt_tokens"),
                        "completion_tokens": tokens.get("completion_tokens"),
                        "total_tokens": tokens.get("total_tokens"),
                    }
                )

        try:
            temp_path.replace(self._config.all_articles_csv_file)
        except PermissionError:
            try:
                # Attempt to remove the target and retry (handles Windows locking edge cases)
                if self._config.all_articles_csv_file.exists():
                    self._config.all_articles_csv_file.unlink()
                temp_path.replace(self._config.all_articles_csv_file)
            except Exception:
                # Final fallback: write temp file as a timestamped fallback
                fallback = self._config.all_articles_csv_file.with_suffix(self._config.all_articles_csv_file.suffix + f".{RUN_ID}.fallback")
                temp_path.replace(fallback)

    def write_individual(self, outcome: ArticleOutcome) -> None:
        record = outcome.to_record()
        record["updated_at"] = _current_timestamp()
        with self._lock:
            self._store_outcome_locked(outcome, record)

    def finalize(self, metadata: Dict[str, Any], trends: List[Dict[str, Any]], statistics: Dict[str, Any]) -> None:
        with self._lock:
            ordered_articles = [self._articles_by_index[index] for index in sorted(self._articles_by_index)]
            master_payload = {
                "metadata": metadata,
                "statistics": statistics,
                "trends": trends,
                "articles": ordered_articles,
            }
            # Write full internal master JSON for analytics and debugging
            master_internal = self._config.output_dir / "master_internal.json"
            _atomic_write_json(master_internal, master_payload, pretty=True)

            # Build public, compact news feed
            public_articles = []
            for a in ordered_articles:
                # required fields
                pub = {
                    "title": a.get("title"),
                    "sentiment": a.get("sentiment"),
                    "category": a.get("category"),
                    "subcategory": a.get("subcategory"),
                    "summary": a.get("summary"),
                }

                # problem fields: required only when sentiment == Problem
                if a.get("sentiment") == "Problem":
                    pub["problem"] = a.get("problem") or None
                    pub["problem_id"] = a.get("problem_id") or None
                else:
                    pub["problem"] = None
                    pub["problem_id"] = None

                # normalize location: convert empty strings to nulls and keep required keys
                loc = a.get("location") or {}
                pub_loc = {
                    "village": loc.get("village") or None,
                    "town": loc.get("town") or None,
                    "mandal": loc.get("mandal") or None,
                    "district": loc.get("district") or None,
                    "state": loc.get("state") or None,
                }
                pub["location"] = pub_loc

                # optional arrays: include only if non-empty
                if a.get("people"):
                    pub["people"] = a.get("people")
                if a.get("entities"):
                    pub["entities"] = a.get("entities")
                if a.get("keywords"):
                    pub["keywords"] = a.get("keywords")

                public_articles.append(pub)

            public_path = self._config.output_dir / "news_output.json"
            _atomic_write_json(public_path, public_articles, pretty=False)

            # Write statistics summary as statistics.json (compact)
            stats_path = self._config.output_dir / "statistics.json"
            _atomic_write_json(stats_path, statistics, pretty=True)

            # persist CSV and legacy failed/duplicate files only when necessary
            self._write_csv_locked(ordered_articles)
            if self._failed_records:
                _atomic_write_json(self._config.failed_articles_file, self._failed_records, pretty=True)

            # Prune extraneous outputs to enforce production layout.
            allowed = {"master_internal.json", "news_output.json", "statistics.json", "api_key_statistics.json"}
            if self._failed_records:
                allowed.add(self._config.failed_articles_file.name)

            # Remove any JSON files not explicitly allowed
            for path in self._config.output_dir.glob("*.json"):
                if path.name not in allowed:
                    try:
                        path.unlink()
                    except Exception:
                        continue

            # Remove legacy CSV and all_articles JSON (not part of final layout)
            try:
                if self._config.all_articles_file.exists():
                    self._config.all_articles_file.unlink()
            except Exception:
                pass
            try:
                if self._config.all_articles_csv_file.exists():
                    self._config.all_articles_csv_file.unlink()
            except Exception:
                pass

            # Remove duplicate and temporary files if present
            for legacy in ("duplicate_articles.json", "processing_statistics.json", "processing_report.json", "quality_report.json", "semantic_score_report.json", "semantic_validation_report.json", "repair_log.json", "validation_report.json", "classification_bias_report.json", "semantic_comparison_report.json", "comparison_report.json"):
                p = self._config.output_dir / legacy
                try:
                    if p.exists():
                        p.unlink()
                except Exception:
                    continue

            # Remove legacy article directories and any stale log naming remnants.
            try:
                for legacy_dir in (self._config.individual_output_dir, self._config.output_dir / "articles"):
                    if legacy_dir.exists() and legacy_dir.is_dir():
                        import shutil

                        shutil.rmtree(legacy_dir)
            except Exception:
                pass

            for stale_log in (self._config.output_dir / "processing_log.txt", self._config.output_dir / "processing_log.log"):
                try:
                    if stale_log.exists():
                        stale_log.unlink()
                except Exception:
                    continue


# ===========================================================
# PROGRESS REPORTING
# ===========================================================


class ProgressReporter:
    """Render a live console progress line with ETA and API key status."""

    def __init__(self, total: int, key_manager: APIKeyManager, logger: logging.Logger) -> None:
        self._total = total
        self._key_manager = key_manager
        self._logger = logger
        self._start = time.monotonic()
        self._lock = threading.Lock()
        self._completed = 0
        self._success = 0
        self._failed = 0
        self._duplicate = 0
        self._last_render = ""

    def update(self, outcome: ArticleOutcome, counts: Dict[str, int]) -> None:
        with self._lock:
            self._completed = counts["completed"]
            self._success = counts["success"]
            self._failed = counts["failed"]
            self._duplicate = counts["duplicate"]
            self._render(outcome)

    def finalize(self) -> None:
        with self._lock:
            self._render(None, final=True)
            sys.stdout.write("\n")
            sys.stdout.flush()

    def _render(self, outcome: Optional[ArticleOutcome], final: bool = False) -> None:
        elapsed = max(0.001, time.monotonic() - self._start)
        processed = self._completed
        remaining = max(0, self._total - processed)
        avg_seconds = elapsed / processed if processed else 0.0
        eta_seconds = avg_seconds * remaining if processed else 0.0
        eta_text = self._format_duration(eta_seconds) if processed else "--:--:--"
        elapsed_text = self._format_duration(elapsed)
        key_index = self._key_manager.last_assigned_key_index
        current_article = outcome.article_id if outcome else "done"

        line = (
            f"[{APP_NAME}] "
            f"{processed}/{self._total} processed | remaining {remaining} | "
            f"success {self._success} | failed {self._failed} | duplicate {self._duplicate} | "
            f"current key #{key_index} | ETA {eta_text} | elapsed {elapsed_text} | {current_article}"
        )

        padding = max(0, len(self._last_render) - len(line))
        sys.stdout.write("\r" + line + (" " * padding))
        sys.stdout.flush()
        self._last_render = line

        if final:
            self._logger.info(line)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ===========================================================
# APPLICATION ORCHESTRATION
# ===========================================================


class TeluguNewsAnalysisApp:
    """Production-ready orchestration for OCR splitting, Groq analysis, validation, and persistence."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.individual_output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = self._configure_logging()
        self.key_manager = APIKeyManager(_discover_api_keys(), config.cooldown_seconds, logger=self.logger)
        self.checkpoint = CheckpointManager(config.checkpoint_file)
        self.output_manager = OutputManager(config, self.logger)
        self.analyzer = GroqAnalyzer(config, self.key_manager, self.logger)
        self.splitter = ArticleSplitter()
        self.entity_extractor = EntityExtractor()
        self.trend_detector = TrendDetector()
        self.statistics_collector = StatisticsCollector()
        self.priority_scheduler = PriorityScheduler()
        self._duplicate_lock = threading.Lock()
        self._seen_hashes = self._initialize_seen_hashes()
        self._problem_id_lock = threading.Lock()
        # Global reports/logs for audit outputs
        self._repair_log: List[Dict[str, Any]] = []
        self._validation_report: List[Dict[str, Any]] = []
        self._quality_report: List[Dict[str, Any]] = []
        self._semantic_report: List[Dict[str, Any]] = []

    def _initialize_seen_hashes(self) -> set[str]:
        seen = set(self.checkpoint.state.get("processed_hashes", []))
        with self.output_manager._lock:
            for record in self.output_manager._articles_by_index.values():
                source_hash = record.get("source_sha256")
                if isinstance(source_hash, str) and source_hash:
                    seen.add(source_hash)
        return seen

    def _configure_logging(self) -> logging.Logger:
        logger = logging.getLogger(APP_NAME)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False

        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(threadName)s | %(message)s")

        file_handler = logging.FileHandler(self.config.processing_log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        # Ensure console logging never fails on Windows consoles with legacy encodings
        try:
            import io

            console_stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
            console_handler = logging.StreamHandler(console_stream)
        except Exception:
            console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        return logger

    def run(self) -> None:
        start_time = time.monotonic()
        self.logger.info("%s started. Run ID=%s", APP_NAME, RUN_ID)

        try:
            if not self.config.input_file.exists():
                raise FileNotFoundError(
                    f"Input file not found: {self.config.input_file.resolve()}"
                )

            raw_text = self.config.input_file.read_text(encoding="utf-8", errors="ignore")
            if not raw_text.strip():
                raise ValueError("Input OCR file is empty")

            articles = self.splitter.split(raw_text)
            if not articles:
                raise ValueError("No articles were detected in the OCR text")

            pending_articles = [article for article in articles if not self.checkpoint.is_processed(article)]
            pending_articles = self.priority_scheduler.prioritize(pending_articles)
            skipped = len(articles) - len(pending_articles)
            if skipped:
                self.logger.info("Skipping %s already-processed article(s) from checkpoint.", skipped)

            if not pending_articles:
                self.logger.info("Nothing left to process. Generating final outputs from existing state.")
                self._finalize_outputs(start_time)
                return

            reporter = ProgressReporter(total=len(pending_articles), key_manager=self.key_manager, logger=self.logger)

            effective_workers = max(1, min(self.config.workers, len(self.key_manager._keys)))
            with ThreadPoolExecutor(max_workers=effective_workers) as executor:
                future_map = {executor.submit(self._process_article, article): article for article in pending_articles}

                for future in as_completed(future_map):
                    article = future_map[future]
                    try:
                        outcome = future.result()
                    except KeyboardInterrupt:
                        raise
                    except Exception as exc:
                        outcome = ArticleOutcome(
                            article_id=article.article_id,
                            article_index=article.article_index,
                            source_sha256=article.source_sha256,
                            status=STATUS_FAILED,
                            error=f"Unexpected worker failure: {exc.__class__.__name__}: {exc}",
                        )
                        self.logger.error(
                            "Worker failure for %s: %s\n%s",
                            article.article_id,
                            outcome.error,
                            traceback.format_exc(),
                        )

                    self.output_manager.write_individual(outcome)
                    self.output_manager.write_record(outcome)
                    self.checkpoint.mark_processed(outcome)
                    self.checkpoint.save()
                    reporter.update(outcome, self.checkpoint.snapshot_counts())

            reporter.finalize()
            self._finalize_outputs(start_time)
            total_elapsed = time.monotonic() - start_time
            self.logger.info("%s finished in %.2fs", APP_NAME, total_elapsed)

        except KeyboardInterrupt:
            self.logger.warning("KeyboardInterrupt received. Saving checkpoint and partial outputs before exit.")
            self.checkpoint.save()
            self._finalize_outputs(start_time)
            raise
        except Exception as exc:
            self.logger.exception("Fatal error: %s", exc)
            self.checkpoint.save()
            self._finalize_outputs(start_time)
            raise

    def _process_article(self, article: ArticleInput) -> ArticleOutcome:
        started = time.monotonic()
        started_at = _current_timestamp()
        article_hash = article.source_sha256
        title_hash = _sha256_hex(Normalizer.normalize_whitespace(article.title))
        worker_name = threading.current_thread().name

        self.logger.info("START article processing | %s", _article_log_context(article, worker_id=worker_name))

        if not self._claim_article_hash(article_hash):
            self.logger.info("FAILURE duplicate detected | %s", _article_log_context(article, worker_id=worker_name))
            return ArticleOutcome(
                article_id=article.article_id,
                article_index=article.article_index,
                source_sha256=article_hash,
                status=STATUS_DUPLICATE,
                duplicate_of=article_hash,
                processing_seconds=time.monotonic() - started,
            )

        if not article.title and not article.content:
            outcome = ArticleOutcome(
                article_id=article.article_id,
                article_index=article.article_index,
                source_sha256=article_hash,
                status=STATUS_FAILED,
                error=f"Corrupted OCR article: empty title and content | {_article_log_context(article, worker_id=worker_name)}",
                processing_seconds=time.monotonic() - started,
            )
            self.logger.warning("FAILURE empty OCR article | %s", _article_log_context(article, worker_id=worker_name))
            return outcome

        if len(article.content) < self.config.empty_article_min_chars:
            outcome = ArticleOutcome(
                article_id=article.article_id,
                article_index=article.article_index,
                source_sha256=article_hash,
                status=STATUS_FAILED,
                error=f"Corrupted OCR article: content too short | {_article_log_context(article, worker_id=worker_name)}",
                processing_seconds=time.monotonic() - started,
            )
            self.logger.warning("FAILURE short OCR article | %s", _article_log_context(article, worker_id=worker_name))
            return outcome

        # New validation pipeline: allow one local repair attempt + one LLM retry for ERRORs
        repair_log_local: List[Dict[str, Any]] = []
        retries_allowed = min(1, max(0, self.config.max_retries))
        retries_remaining = retries_allowed

        last_error_text = None
        while True:
            try:
                parsed = self.analyzer.analyze(article)
                analysis = AnalysisValidator.normalize(parsed.data)

                # populate IDs and extract entities
                if analysis.get("sentiment") == "Problem":
                    with self._problem_id_lock:
                        analysis["problem_id"] = ProblemIDGenerator.generate(
                            analysis.get("category", ""),
                            analysis.get("location", {}).get("district", ""),
                            analysis.get("problem") or "",
                        )

                analysis["article_id"] = article.article_id
                analysis["article_index"] = article.article_index
                analysis["article_hash"] = article_hash
                analysis["title_hash"] = title_hash
                analysis["trend_id"] = None
                analysis["entities"] = self.entity_extractor.extract(article, analysis)

                # LLM-first policy: Groq is the single source of semantic truth.
                # Do not perform any keyword- or rule-based reclassification here.
                orig_category = parsed.data.get("category") if isinstance(parsed, type(parsed)) else analysis.get("category")
                orig_sentiment = parsed.data.get("sentiment") if isinstance(parsed, type(parsed)) else analysis.get("sentiment")

                # Record Groq-originated semantic fields for audit. Python will only normalize values
                # via AnalysisValidator.normalize and will not override Groq's category/sentiment/subcategory.
                try:
                    self._semantic_report.append({
                        "article_id": article.article_id,
                        "article_index": article.article_index,
                        "groq_category": parsed.data.get("category") if hasattr(parsed, 'data') else analysis.get("category"),
                        "groq_sentiment": parsed.data.get("sentiment") if hasattr(parsed, 'data') else analysis.get("sentiment"),
                        "final_category": analysis.get("category"),
                        "final_sentiment": analysis.get("sentiment"),
                        "timestamp": _current_timestamp(),
                        "source": "groq",
                    })
                except Exception:
                    self._semantic_report.append({
                        "article_id": article.article_id,
                        "article_index": article.article_index,
                        "final_category": analysis.get("category"),
                        "final_sentiment": analysis.get("sentiment"),
                        "timestamp": _current_timestamp(),
                        "source": "groq_error",
                    })

                # Run deterministic validation engine (it may append repairs to repair_log_local)
                validation_results = ValidationEngine.run(analysis, repair_log_local, self.logger)
                # record validation results globally for final reports
                for r in validation_results:
                    entry = dict(r)
                    entry.update({"article_id": article.article_id, "article_index": article.article_index, "timestamp": _current_timestamp()})
                    self._validation_report.append(entry)

                decision = DecisionEngine.decide(validation_results, retries_remaining)

                if decision == "accept":
                    processing_seconds = time.monotonic() - started
                    analysis["processing"] = {
                        "model": self.config.model_name,
                        "processing_time_ms": int(round(processing_seconds * 1000)),
                        "retry_count": max(0, parsed.attempts - 1),
                        "api_key_index": parsed.api_key_index,
                        "timestamp": _current_timestamp(),
                    }

                    # compute quality score using the new engine
                    quality = QualityAssessmentEngine.compute(analysis, len(repair_log_local))
                    analysis["quality_score"] = quality
                    self._quality_report.append({"article_id": article.article_id, "quality_score": quality, "timestamp": _current_timestamp()})

                    # persist repair_log entries to global log with article context
                    for entry in repair_log_local:
                        entry.update({"article_id": article.article_id, "article_index": article.article_index})
                        self._repair_log.append(entry)

                    self.logger.info(
                        "SUCCESS article processed in %.3fs | %s | api_key=%s | retry=%s | thread=%s",
                        processing_seconds,
                        _article_log_context(article, worker_id=worker_name, api_key_index=parsed.api_key_index, retry_count=max(0, parsed.attempts - 1)),
                        parsed.api_key_index,
                        max(0, parsed.attempts - 1),
                        worker_name,
                    )

                    return ArticleOutcome(
                        article_id=article.article_id,
                        article_index=article.article_index,
                        source_sha256=article_hash,
                        status=STATUS_SUCCESS,
                        analysis=analysis,
                        api_key_index=parsed.api_key_index,
                        retry_count=max(0, parsed.attempts - 1),
                        processing_seconds=processing_seconds,
                        tokens=parsed.tokens,
                    )

                if decision == "retry":
                    # allow one LLM retry for ERRORs only
                    self.logger.info("Validation errors require LLM retry, attempts remaining=%s | %s", retries_remaining, _article_log_context(article, worker_id=worker_name))
                    retries_remaining -= 1
                    # loop and call analyzer.analyze again
                    continue

                # decision == 'reject'
                # Gather failure reasons and return failed outcome
                reasons = [f"{r.get('severity')}:{r.get('field')}:{r.get('message')}" for r in validation_results]
                error_text = (
                    f"Validation rejected article | reasons={'|'.join(reasons)} | {_article_log_context(article, worker_id=worker_name)}"
                )
                self.logger.warning("FAILURE validation reject | %s", error_text)
                return ArticleOutcome(
                    article_id=article.article_id,
                    article_index=article.article_index,
                    source_sha256=article_hash,
                    status=STATUS_FAILED,
                    error=error_text,
                    processing_seconds=time.monotonic() - started,
                )

            except Exception as exc:
                # Non-retryable or unexpected exception: log and fail
                last_error_text = f"{exc.__class__.__name__}: {exc}"
                self.logger.error("FAILURE article processing | %s | %s", last_error_text, _article_log_context(article, worker_id=worker_name))
                return ArticleOutcome(
                    article_id=article.article_id,
                    article_index=article.article_index,
                    source_sha256=article_hash,
                    status=STATUS_FAILED,
                    error=f"Analysis failed: {last_error_text}",
                    processing_seconds=time.monotonic() - started,
                )

    def _claim_article_hash(self, source_sha256: str) -> bool:
        with self._duplicate_lock:
            if source_sha256 in self._seen_hashes:
                return False
            self._seen_hashes.add(source_sha256)
            return True

    def _quality_score(self, article: Dict[str, Any]) -> float:
        score = 0.0
        summary = article.get("summary", "")
        score += min(0.35, len(summary) / 400.0)
        score += 0.2 if article.get("people") else 0.0
        score += 0.15 if article.get("entities") else 0.0
        score += 0.1 if article.get("keywords") else 0.0
        score += 0.2 if article.get("problem_id") or article.get("sentiment") != "Problem" else 0.0
        return int(round(min(1.0, score) * 100))

    def _finalize_outputs(self, start_time: float) -> None:
        with self.output_manager._lock:
            articles = [self.output_manager._articles_by_index[index] for index in sorted(self.output_manager._articles_by_index)]
            failed_records = list(self.output_manager._failed_records)
            duplicate_records = list(self.output_manager._duplicate_records)

        trends = self.trend_detector.build(articles)
        for article in articles:
            if article.get("sentiment") == "Problem":
                article["trend_id"] = self._trend_id_for_article(article, trends)

        statistics = self.statistics_collector.build(articles, duplicate_records, failed_records)
        metadata = {
            "generated_at": _current_timestamp(),
            "model": self.config.model_name,
            "processing_time": round(time.monotonic() - start_time, 3),
            "total_articles": len(articles) + len(duplicate_records) + len(failed_records),
            "processed": len(articles),
            "failed": len(failed_records),
            "duplicates": len(duplicate_records),
        }

        # Final outputs are produced by OutputManager.finalize. Per production policy
        # emit only the internal master file and a compact public feed; avoid extra
        # diagnostic JSON files unless real failures occurred.
        self.key_manager.write_statistics_file(self.config.output_dir / "api_key_statistics.json")
        self.output_manager.finalize(metadata, trends, statistics)
        self.checkpoint.save()

    def _trend_id_for_article(self, article: Dict[str, Any], trends: List[Dict[str, Any]]) -> Optional[str]:
        for trend in trends:
            if (
                trend.get("category") == article.get("category")
                and trend.get("subcategory") == article.get("subcategory")
                and trend.get("district") == article.get("location", {}).get("district")
            ):
                problem = Normalizer.normalize_whitespace(article.get("problem") or article.get("summary") or "")
                if SequenceMatcher(None, problem, trend.get("seed_problem", "")).ratio() >= 0.78:
                    return trend["trend_id"]
        return None


# ===========================================================
# CLI
# ===========================================================


def _parse_args(argv: Sequence[str]) -> AppConfig:
    import argparse

    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--input", dest="input_file", default=str(INPUT_FILE), help="Path to the OCR .txt file")
    parser.add_argument("--output-dir", dest="output_dir", default=str(OUTPUT_DIR), help="Directory for output files")
    parser.add_argument("--workers", dest="workers", type=int, default=DEFAULT_WORKERS, help="Parallel worker count")
    parser.add_argument("--model", dest="model_name", default=MODEL_NAME, help="Groq model name")
    parser.add_argument("--temperature", dest="temperature", type=float, default=TEMPERATURE, help="Model temperature")
    parser.add_argument("--timeout", dest="request_timeout_seconds", type=float, default=REQUEST_TIMEOUT_SECONDS, help="Request timeout in seconds")
    parser.add_argument("--retries", dest="max_retries", type=int, default=MAX_RETRIES, help="Maximum retries per article")
    parser.add_argument("--cooldown", dest="cooldown_seconds", type=float, default=COOLDOWN_SECONDS, help="API key cooldown after failure")
    parser.add_argument("--empty-min-chars", dest="empty_article_min_chars", type=int, default=EMPTY_ARTICLE_MIN_CHARS, help="Minimum article content length")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    return AppConfig(
        input_file=Path(args.input_file),
        output_dir=output_dir,
        individual_output_dir=output_dir / "individual_articles",
        checkpoint_file=Path("checkpoint.json"),
        all_articles_file=output_dir / "all_articles.json",
        all_articles_csv_file=output_dir / "all_articles.csv",
        failed_articles_file=output_dir / "failed_articles.json",
        processing_log_file=output_dir / "processing.log",
        model_name=args.model_name,
        temperature=args.temperature,
        request_timeout_seconds=args.request_timeout_seconds,
        workers=args.workers,
        max_retries=args.max_retries,
        cooldown_seconds=args.cooldown_seconds,
        empty_article_min_chars=args.empty_article_min_chars,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        config = _parse_args(argv)
        app = TeluguNewsAnalysisApp(config)
        app.run()
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())