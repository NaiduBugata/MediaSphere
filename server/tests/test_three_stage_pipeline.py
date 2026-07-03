import unittest

from telugu_ai_news_analyzer import GroqAnalyzer, Normalizer


class ThreeStagePipelineTests(unittest.TestCase):
    def test_merge_stage_payloads_builds_unified_article(self):
        article = type("Article", (), {"title": "శ్రీకారం", "content": "వివాదం"})()
        merged = GroqAnalyzer._merge_stage_payloads(
            {
                "sentiment": "Problem",
                "category": "Roads",
                "subcategory": "Potholes",
                "problem": "రహదారి బోలు",
                "severity": "High",
                "authority": "జిల్లా administer",
            },
            {
                "location": {"district": "గుంటూరు", "mandal": "మంగళగిరి", "state": "Andhra Pradesh"},
                "people": [{"name": "రమేష్", "designation": "నగర నివాసి"}],
                "entities": [{"type": "Person", "name": "రమేష్", "normalized": "రమేష్"}],
                "keywords": ["వార్త", "ప్రజలు", "సమావేశం", "వివాదం", "పరిష్కారం"],
            },
            {"summary": "ఈ కథనం ప్రజల సమస్యను స్పష్టంగా వివరిస్తుంది మరియు పరిష్కార చర్యలపై దృష్టి పెడుతుంది."},
            article,
        )

        self.assertEqual(merged["title"], "శ్రీకారం")
        self.assertEqual(merged["sentiment"], "Problem")
        self.assertEqual(merged["category"], "Roads")
        self.assertEqual(merged["subcategory"], "Potholes")
        self.assertEqual(merged["problem"], "రహదారి బోలు")
        self.assertEqual(merged["summary"].split()[0], "ఈ")
        self.assertIsNone(merged["problem_id"])
        self.assertEqual(merged["location"]["district"], "Guntur")
        self.assertEqual(merged["location"]["state"], "Andhra Pradesh")
        self.assertEqual(len(merged["keywords"]), 5)

    def test_normalize_location_converts_unknown_values_to_none(self):
        location = Normalizer.normalize_location({"district": "", "mandal": "", "village": "", "town": ""})
        self.assertIsNone(location["district"])
        self.assertIsNone(location["mandal"])
        self.assertIsNone(location["village"])
        self.assertIsNone(location["town"])
        self.assertEqual(location["state"], "Andhra Pradesh")

    def test_summary_stage_output_accepts_short_summary(self):
        summary, words = GroqAnalyzer._evaluate_summary_stage_output("ఈ కథనం ప్రజల సమస్యను వివరిస్తుంది.", title="శ్రీకారం")
        self.assertEqual(summary, "ఈ కథనం ప్రజల సమస్యను వివరిస్తుంది.")
        self.assertEqual(words, 5)

    def test_normalize_category_handles_common_aliases(self):
        self.assertEqual(Normalizer.normalize_category("labour"), "Employment")
        self.assertEqual(Normalizer.normalize_category("విద్య"), "Education")


if __name__ == "__main__":
    unittest.main()
