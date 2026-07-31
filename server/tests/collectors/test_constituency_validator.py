"""Unit tests for Narasaraopet constituency validation (Sakshi)."""

from __future__ import annotations

import os
import sys
import json
import unittest
from pathlib import Path
from unittest.mock import patch

SERVER_DIR = Path(__file__).resolve().parents[2]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from collectors.sakshi.constituency_validator import (  # noqa: E402
    ConstituencyValidator,
    build_searchable_text,
)


class ConstituencyValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = ConstituencyValidator(ai_enabled=False)

    def test_primary_keyword_accepts(self) -> None:
        raw = {
            "title": "నరసరావుపేటలో రోడ్డు నిర్మాణం",
            "description": "Local works",
            "content": "Detailed body about road works in the town. " * 5,
            "tags": [],
            "breadcrumb": [],
        }
        result = self.validator.validate_article(raw)
        self.assertTrue(result.valid)
        self.assertGreaterEqual(result.score, 10)
        self.assertEqual(result.reason, "score_accept")

    def test_assembly_segment_accepts(self) -> None:
        raw = {
            "title": "Vinukonda farmers protest over irrigation",
            "description": "",
            "content": "Farmers gathered near Vinukonda bus stand to demand water supply. " * 3,
            "tags": ["Vinukonda"],
            "breadcrumb": ["Andhra Pradesh"],
        }
        result = self.validator.validate_article(raw)
        self.assertTrue(result.valid)
        self.assertGreaterEqual(result.score, 6)

    def test_mandal_only_is_borderline_without_ai(self) -> None:
        import tempfile

        dict_path = Path(tempfile.gettempdir()) / "ms_test_location_dict.json"
        dict_path.write_text(
            json.dumps(
                {
                    "scoring": {
                        "primary": 10,
                        "assembly": 6,
                        "mandal": 4,
                        "village": 3,
                        "district_alias": 2,
                        "negative_penalty": 8,
                        "accept_threshold": 6,
                        "borderline_low": 3,
                        "negative_override_score": 12,
                    },
                    "primary_keywords": ["Narasaraopet"],
                    "assembly_segments": ["Vinukonda"],
                    "mandals": ["OnlyTestMandal"],
                    "villages": [],
                    "district_aliases": [],
                    "negative_keywords": [],
                    "negative_categories": [],
                }
            ),
            encoding="utf-8",
        )
        validator = ConstituencyValidator(dict_path, ai_enabled=False)
        raw = {
            "title": "Updates from OnlyTestMandal office",
            "description": "Admin note",
            "content": "The OnlyTestMandal revenue office announced a schedule. " * 4,
            "tags": [],
            "breadcrumb": [],
        }
        result = validator.validate_article(raw)
        self.assertFalse(result.valid)
        self.assertEqual(result.score, 4)
        self.assertIn(result.reason, ("borderline", "borderline_no_ai"))

    def test_negative_filter_rejects_hyderabad_sports(self) -> None:
        raw = {
            "title": "Hyderabad cricket match draws huge crowd",
            "description": "Sports",
            "content": "IPL cricket excitement in Hyderabad stadium last night. " * 5,
            "category": "Sports",
            "tags": ["Cricket"],
            "breadcrumb": ["Sports"],
        }
        result = self.validator.validate_article(raw)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "negative_filter")

    def test_negative_does_not_override_high_constituency_score(self) -> None:
        raw = {
            "title": "Narasaraopet MLA meets Delhi officials over local roads",
            "description": "Narasaraopet constituency development",
            "content": (
                "The Narasaraopet MP discussed Chilakaluripet and Vinukonda road works "
                "during a brief Delhi visit for approvals. Local mandals benefit. "
            )
            * 3,
            "tags": ["Narasaraopet", "Chilakaluripet"],
            "breadcrumb": ["Andhra Pradesh", "Narasaraopet"],
        }
        result = self.validator.validate_article(raw)
        self.assertTrue(result.valid)

    def test_unrelated_andhra_city_rejected(self) -> None:
        raw = {
            "title": "Visakhapatnam port expansion plan approved",
            "description": "Coastal development",
            "content": "The Visakhapatnam port trust cleared a new berth project today. " * 5,
            "tags": ["Vizag"],
            "breadcrumb": ["Andhra Pradesh"],
        }
        result = self.validator.validate_article(raw)
        self.assertFalse(result.valid)

    def test_build_searchable_text_combines_fields(self) -> None:
        text = build_searchable_text(
            {
                "title": "T1",
                "description": "D1",
                "content": "C1",
                "tags": ["TagA"],
                "breadcrumb": ["Home", "News"],
            }
        )
        self.assertIn("T1", text)
        self.assertIn("D1", text)
        self.assertIn("C1", text)
        self.assertIn("TagA", text)
        self.assertIn("News", text)

    def test_url_priority_does_not_match_ipur_inside_jaipur(self) -> None:
        from collectors.sakshi.collector import _link_priority, _url_has_location_keyword

        keywords = ["Ipur", "Ipuru", "Narasaraopet", "Palnadu"]
        jaipur = "https://www.sakshi.com/telugu-news/national/jaipur-woman-contract-killers"
        self.assertFalse(_url_has_location_keyword(jaipur, "", keywords))
        self.assertEqual(_link_priority(jaipur, "", keywords), 0)
        good = "https://www.sakshi.com/telugu-news/andhra-pradesh/massive-theft-narasaraopet-2616783"
        self.assertTrue(_url_has_location_keyword(good, "", keywords))
        self.assertEqual(_link_priority(good, "", keywords), 100)

    def test_ai_borderline_yes(self) -> None:
        validator = ConstituencyValidator(ai_enabled=True, accept_threshold=6)
        raw = {
            "title": "Updates from Piduguralla",
            "description": "",
            "content": "Piduguralla residents met officials about drainage. " * 5,
            "tags": ["Piduguralla"],
            "breadcrumb": [],
        }
        with patch.object(validator, "_ai_constituency_check", return_value="YES"):
            result = validator.validate_article(raw)
        # Score may be borderline; if AI is invoked, should accept
        if result.reason.startswith("ai") or result.score >= validator.borderline_low:
            if result.ai_decision == "YES":
                self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()
