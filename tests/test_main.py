import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class CoroutineSpeedupTests(unittest.TestCase):
    def test_shared_client_respects_arxiv_rate_limit(self):
        booster = main.CoroutineSpeedup()

        self.assertGreaterEqual(booster.arxiv_client.delay_seconds, 3.0)
        self.assertGreaterEqual(booster.arxiv_client.num_retries, 5)

    def test_unicode_markdown_is_written_as_utf8(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "nested" / "docs"
            storage_dir = root / "nested" / "database" / "storage"
            storage_pattern = str(storage_dir / "storage_{}.md")

            with patch.multiple(
                    main,
                    SERVER_PATH_DOCS=str(docs_dir),
                    SERVER_DIR_STORAGE=str(storage_dir),
                    SERVER_PATH_STORAGE_MD=storage_pattern,
            ):
                booster = main.CoroutineSpeedup()
                booster.channel.put_nowait({
                    "paper": {
                        "test-paper": {
                            "publish_time": "2026-08-21",
                            "title": "Señorita aerosol retrieval",
                            "authors": "Muñoz et.al.",
                            "id": "2608.00001v1",
                            "paper_url": "https://arxiv.org/abs/2608.00001v1",
                            "repo": "null",
                        },
                    },
                    "topic": "Atmospheric AI",
                    "subtopic": "Unicode metadata",
                    "fields": ["Publish Date", "Title", "Authors", "PDF", "Code"],
                })

                booster.overload_tasks()

            docs_text = (
                docs_dir / "Atmospheric AI" / "Unicode metadata.md"
            ).read_text(encoding="utf8")
            storage_text = Path(
                storage_pattern.format(main.ToolBox.log_date("file"))
            ).read_text(encoding="utf8")

            self.assertIn("Señorita", docs_text)
            self.assertIn("Muñoz", docs_text)
            self.assertIn("Señorita", storage_text)
            self.assertIn("Muñoz", storage_text)


if __name__ == "__main__":
    unittest.main()
