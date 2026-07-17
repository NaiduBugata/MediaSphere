"""Narasaraopet Parliamentary Constituency multi-stage article validator."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("collectors.sakshi.constituency_validator")

_DEFAULT_DICT_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "location_dictionary.json"


@dataclass
class ValidationResult:
    """Outcome of constituency validation for one article."""

    valid: bool
    score: int
    reason: str
    matched_primary: list[str] = field(default_factory=list)
    matched_assembly: list[str] = field(default_factory=list)
    matched_mandals: list[str] = field(default_factory=list)
    matched_villages: list[str] = field(default_factory=list)
    matched_negative: list[str] = field(default_factory=list)
    ai_decision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "score": self.score,
            "reason": self.reason,
            "matched_primary": self.matched_primary,
            "matched_assembly": self.matched_assembly,
            "matched_mandals": self.matched_mandals,
            "matched_villages": self.matched_villages,
            "matched_negative": self.matched_negative,
            "ai_decision": self.ai_decision,
        }


def _normalize_for_match(text: str) -> str:
    """Lowercase Latin text; keep Telugu as-is for substring matching."""
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _find_matches(haystack: str, keywords: list[str]) -> list[str]:
    """Return keywords that appear in haystack (case-insensitive for Latin)."""
    found: list[str] = []
    hay_lower = haystack.lower()
    for keyword in keywords:
        if not keyword:
            continue
        # Telugu / non-ASCII: exact substring on original-case haystack and lower
        if any(ord(ch) > 127 for ch in keyword):
            if keyword in haystack or keyword in hay_lower:
                found.append(keyword)
            continue
        pattern = re.escape(keyword.lower())
        # Word-boundary-ish for multi-word English place names
        if re.search(rf"(?<!\w){pattern}(?!\w)", hay_lower, re.IGNORECASE):
            found.append(keyword)
        elif keyword.lower() in hay_lower and " " in keyword.lower():
            found.append(keyword)
    return found


def build_searchable_text(raw: dict[str, Any]) -> str:
    """Stage 3: combine title + description + body + tags + breadcrumb."""
    parts: list[str] = []
    for key in ("title", "description", "summary", "og_description", "content", "article", "category"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    tags = raw.get("tags") or []
    if isinstance(tags, list):
        parts.extend(str(t).strip() for t in tags if t)
    breadcrumb = raw.get("breadcrumb") or []
    if isinstance(breadcrumb, list):
        parts.extend(str(b).strip() for b in breadcrumb if b)
    elif isinstance(breadcrumb, str) and breadcrumb.strip():
        parts.append(breadcrumb.strip())
    location = raw.get("location")
    if isinstance(location, dict):
        for loc_key in ("district", "mandal", "village", "town", "state"):
            loc_val = location.get(loc_key)
            if loc_val:
                parts.append(str(loc_val))
    return "\n".join(parts)


class ConstituencyValidator:
    """Score articles against the Narasaraopet Parliamentary Constituency dictionary."""

    def __init__(
        self,
        dictionary_path: Path | str | None = None,
        *,
        accept_threshold: int | None = None,
        ai_enabled: bool | None = None,
    ) -> None:
        path = Path(dictionary_path) if dictionary_path else _DEFAULT_DICT_PATH
        self.dictionary_path = path
        self._data = self._load(path)
        scoring = self._data.get("scoring") or {}
        self.weights = {
            "primary": int(scoring.get("primary", 10)),
            "assembly": int(scoring.get("assembly", 6)),
            "mandal": int(scoring.get("mandal", 4)),
            "village": int(scoring.get("village", 3)),
            "district_alias": int(scoring.get("district_alias", 2)),
            "negative_penalty": int(scoring.get("negative_penalty", 8)),
        }
        env_threshold = os.getenv("SAKSHI_CONSTITUENCY_SCORE_THRESHOLD", "").strip()
        if accept_threshold is not None:
            self.accept_threshold = accept_threshold
        elif env_threshold:
            self.accept_threshold = int(env_threshold)
        else:
            self.accept_threshold = int(scoring.get("accept_threshold", 6))

        self.borderline_low = int(scoring.get("borderline_low", 3))
        self.negative_override_score = int(scoring.get("negative_override_score", 12))

        ai_cfg = self._data.get("ai_validation") or {}
        if ai_enabled is not None:
            self.ai_enabled = ai_enabled
        else:
            env_ai = os.getenv("SAKSHI_AI_VALIDATION", "").strip().lower()
            if env_ai in ("1", "true", "yes", "on"):
                self.ai_enabled = True
            elif env_ai in ("0", "false", "no", "off"):
                self.ai_enabled = False
            else:
                self.ai_enabled = bool(ai_cfg.get("enabled", True))

        self.primary = list(self._data.get("primary_keywords") or [])
        self.assembly = list(self._data.get("assembly_segments") or [])
        self.mandals = list(self._data.get("mandals") or [])
        self.villages = list(self._data.get("villages") or [])
        self.district_aliases = list(self._data.get("district_aliases") or [])
        self.negative_keywords = list(self._data.get("negative_keywords") or [])
        self.negative_categories = list(self._data.get("negative_categories") or [])
        self.constituency_name = self._data.get("constituency") or "Narasaraopet Parliamentary Constituency"

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Location dictionary not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def score_text(self, text: str, *, category: str = "") -> ValidationResult:
        """Compute constituency score and preliminary validity (before AI)."""
        matched_primary = _find_matches(text, self.primary)
        matched_assembly = _find_matches(text, self.assembly)
        matched_mandals = _find_matches(text, self.mandals)
        matched_villages = _find_matches(text, self.villages)
        matched_district = _find_matches(text, self.district_aliases)
        matched_negative = _find_matches(text, self.negative_keywords)

        # Category negatives (avoid double-counting same tokens)
        cat_text = category or ""
        for neg_cat in self.negative_categories:
            if neg_cat and neg_cat.lower() in cat_text.lower():
                if neg_cat not in matched_negative:
                    matched_negative.append(neg_cat)

        score = 0
        if matched_primary:
            score += self.weights["primary"]
        if matched_assembly:
            # Cap assembly contribution to one tier + small multi-match bonus
            score += self.weights["assembly"]
            if len(matched_assembly) > 1:
                score += min(4, (len(matched_assembly) - 1) * 2)
        if matched_mandals:
            score += self.weights["mandal"]
            if len(matched_mandals) > 1:
                score += min(4, (len(matched_mandals) - 1) * 2)
        if matched_villages:
            score += self.weights["village"]
            if len(matched_villages) > 1:
                score += min(3, (len(matched_villages) - 1))
        if matched_district and not matched_primary and not matched_assembly and not matched_mandals:
            # District alone is weak signal (Palnadu is broader than constituency)
            score += self.weights["district_alias"]

        negative_hit = bool(matched_negative)
        if negative_hit and score < self.negative_override_score:
            score = max(0, score - self.weights["negative_penalty"])
            return ValidationResult(
                valid=False,
                score=score,
                reason="negative_filter",
                matched_primary=matched_primary,
                matched_assembly=matched_assembly,
                matched_mandals=matched_mandals,
                matched_villages=matched_villages,
                matched_negative=matched_negative,
            )

        if score >= self.accept_threshold:
            return ValidationResult(
                valid=True,
                score=score,
                reason="score_accept",
                matched_primary=matched_primary,
                matched_assembly=matched_assembly,
                matched_mandals=matched_mandals,
                matched_villages=matched_villages,
                matched_negative=matched_negative,
            )

        if score >= self.borderline_low:
            return ValidationResult(
                valid=False,
                score=score,
                reason="borderline",
                matched_primary=matched_primary,
                matched_assembly=matched_assembly,
                matched_mandals=matched_mandals,
                matched_villages=matched_villages,
                matched_negative=matched_negative,
            )

        return ValidationResult(
            valid=False,
            score=score,
            reason="score_below_threshold",
            matched_primary=matched_primary,
            matched_assembly=matched_assembly,
            matched_mandals=matched_mandals,
            matched_villages=matched_villages,
            matched_negative=matched_negative,
        )

    def validate_article(self, raw: dict[str, Any], *, use_ai: bool | None = None) -> ValidationResult:
        """
        Full validation pipeline for one fetched Sakshi article.

        Stages 3–4: build searchable text, score, optional AI for borderline.
        """
        text = build_searchable_text(raw)
        category = str(raw.get("category") or "")
        result = self.score_text(text, category=category)

        if result.valid:
            return result

        if result.reason != "borderline":
            return result

        should_ai = self.ai_enabled if use_ai is None else use_ai
        if not should_ai:
            result.reason = "borderline_no_ai"
            return result

        decision = self._ai_constituency_check(raw, text)
        result.ai_decision = decision
        if decision == "YES":
            result.valid = True
            result.reason = "ai_yes"
        elif decision == "NO":
            result.valid = False
            result.reason = "ai_no"
        else:
            result.valid = False
            result.reason = "ai_uncertain"

        return result

    def _ai_constituency_check(self, raw: dict[str, Any], text: str) -> str:
        """Ask Groq only for borderline articles. Returns YES / NO / UNCERTAIN."""
        try:
            from pipeline_config import discover_groq_keys
        except Exception:  # noqa: BLE001
            try:
                from config.settings import discover_groq_keys
            except Exception:  # noqa: BLE001
                logger.warning("AI validation skipped: cannot discover Groq keys")
                return "UNCERTAIN"

        keys = discover_groq_keys()
        if not keys:
            logger.warning("AI validation skipped: no GROQ_API_KEY configured")
            return "UNCERTAIN"

        title = (raw.get("title") or "")[:300]
        snippet = text[:2500]
        prompt = (
            f"Does this Telugu/English news article primarily belong to the "
            f"{self.constituency_name} in Andhra Pradesh (Palnadu district), "
            f"including its assembly segments (Pedakurapadu, Chilakaluripet, "
            f"Narasaraopet, Sattenapalle, Vinukonda, Gurazala, Macherla) and "
            f"their mandals/villages?\n\n"
            f"Answer with exactly one word: YES, NO, or UNCERTAIN.\n\n"
            f"Title: {title}\n\nArticle excerpt:\n{snippet}"
        )

        try:
            from groq import Groq

            client = Groq(api_key=keys[0])
            response = client.chat.completions.create(
                model=os.getenv("SAKSHI_AI_VALIDATION_MODEL", "llama-3.1-8b-instant"),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You classify whether a news article is primarily about "
                            "the Narasaraopet Parliamentary Constituency. Reply with "
                            "only YES, NO, or UNCERTAIN."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=10,
            )
            content = (response.choices[0].message.content or "").strip().upper()
            for token in ("YES", "NO", "UNCERTAIN"):
                if token in content:
                    logger.info("AI constituency check: %s | title=%r", token, title[:80])
                    return token
            return "UNCERTAIN"
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI constituency check failed: %s", exc)
            return "UNCERTAIN"


# Module-level singleton for collector reuse
_default_validator: ConstituencyValidator | None = None


def get_validator() -> ConstituencyValidator:
    global _default_validator
    if _default_validator is None:
        _default_validator = ConstituencyValidator()
    return _default_validator
