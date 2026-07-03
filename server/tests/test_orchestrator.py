import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate_article_txt
import orchestrator as orchestrator_module


class PipelineOrchestratorTests(unittest.TestCase):
    def test_stage_generate_article_skips_when_csv_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            csv_path = temp_path / "news.csv"
            article_path = temp_path / "article.txt"
            csv_path.write_text("id,title,date,content\n", encoding="utf-8-sig")

            with patch.object(orchestrator_module, "CSV_PATH", csv_path), patch.object(orchestrator_module, "ARTICLE_PATH", article_path), patch.object(generate_article_txt, "CSV_PATH", csv_path), patch.object(generate_article_txt, "ARTICLE_PATH", article_path):
                result = orchestrator_module.PipelineOrchestrator().stage_generate_article()

            self.assertEqual(result.status, "SKIPPED")


if __name__ == "__main__":
    unittest.main()
