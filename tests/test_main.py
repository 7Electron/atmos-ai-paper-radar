import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from translator import TitleTranslator


class MarkdownGenerationTests(unittest.TestCase):
    def test_arxiv_client_respects_service_rate_limit(self):
        booster = main.CoroutineSpeedup()
        self.assertGreaterEqual(booster.arxiv_client.delay_seconds, 3.0)
        self.assertGreaterEqual(booster.arxiv_client.num_retries, 5)

    def test_unicode_paper_metadata_is_written_as_utf8(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            storage = root / "database" / "storage"
            storage_template = str(storage / "storage_{}.md")
            translation_cache = root / "database" / "title_translations.json"

            with patch.dict("os.environ", {"OPENAI_API_KEY": ""}), patch.multiple(
                    main,
                    SERVER_PATH_DOCS=str(docs),
                    SERVER_DIR_STORAGE=str(storage),
                    SERVER_PATH_STORAGE_MD=storage_template,
                    SERVER_PATH_README=str(root / "README.md"),
                    SERVER_PATH_TRANSLATION_CACHE=str(translation_cache),
            ):
                booster = main.CoroutineSpeedup()
                booster.channel.put_nowait({
                    "paper": {
                        "2608.00001": {
                            "publish_time": "2026-08-21",
                            "title": "Señorita aerosols",
                            "translated_title": "",
                            "authors": "Muñoz et.al.",
                            "id": "2608.00001v1",
                            "paper_url": "https://arxiv.org/abs/2608.00001v1",
                            "journal": "Journal of Atmospheric Science",
                            "repo": "null",
                        }
                    },
                    "topic": "Atmosphere",
                    "subtopic": "Aerosols",
                    "fields": [
                        "Publish Date",
                        "Title",
                        "中文译名",
                        "Authors",
                        "PDF",
                        "期刊 / 会议（原文）",
                        "Code",
                    ],
                })

                booster.overload_tasks()

                output = (docs / "Atmosphere" / "Aerosols.md").read_text(encoding="utf8")
                self.assertIn("Señorita aerosols", output)
                self.assertIn("Muñoz", output)
                self.assertIn("中文译名", output)
                self.assertIn("未翻译", output)
                self.assertIn("Journal of Atmospheric Science", output)

    def test_translator_preserves_chinese_titles_without_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            translator = TitleTranslator(
                Path(temp_dir) / "translations.json",
                api_key="",
            )

            translated = translator.translate_many([
                "大气气溶胶反演方法",
                "Atmospheric aerosol retrieval",
                "大気エアロゾルの検索",
            ])

            self.assertEqual(translated["大气气溶胶反演方法"], "大气气溶胶反演方法")
            self.assertEqual(translated["Atmospheric aerosol retrieval"], "未翻译")
            self.assertEqual(translated["大気エアロゾルの検索"], "未翻译")

    def test_translator_caches_successful_translations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "translations.json"
            translator = TitleTranslator(cache_path, api_key="test-key")

            with patch.object(
                translator,
                "_request_translations",
                return_value=["大气气溶胶反演"],
            ) as request_translations:
                translated = translator.translate_many([
                    "Atmospheric aerosol retrieval"
                ])

            self.assertEqual(
                translated["Atmospheric aerosol retrieval"],
                "大气气溶胶反演",
            )
            request_translations.assert_called_once()

            cached = TitleTranslator(cache_path, api_key="")
            self.assertEqual(
                cached.translate_many(["Atmospheric aerosol retrieval"])[
                    "Atmospheric aerosol retrieval"
                ],
                "大气气溶胶反演",
            )


if __name__ == "__main__":
    unittest.main()
