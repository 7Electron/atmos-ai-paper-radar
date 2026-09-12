import json
import os
import re
from pathlib import Path

import requests

from config import logger


class TitleTranslator:
    """Translate non-Chinese paper titles and persist successful results."""

    _chinese_pattern = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
    _japanese_pattern = re.compile(r"[\u3040-\u30ff]")
    _korean_pattern = re.compile(r"[\uac00-\ud7af]")
    _endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, cache_path, api_key=None, model=None):
        self.cache_path = Path(cache_path)
        self.api_key = (
            api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        ).strip()
        self.model = model or os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-5-mini")
        self.cache = self._load_cache()

    @classmethod
    def contains_chinese(cls, text):
        text = text or ""
        return (
            bool(cls._chinese_pattern.search(text))
            and not cls._japanese_pattern.search(text)
            and not cls._korean_pattern.search(text)
        )

    def _load_cache(self):
        if not self.cache_path.exists():
            return {}
        try:
            with self.cache_path.open("r", encoding="utf8") as cache_file:
                data = json.load(cache_file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Could not load title translation cache: {exc}")
            return {}

    def _save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("w", encoding="utf8") as cache_file:
            json.dump(
                self.cache,
                cache_file,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            cache_file.write("\n")

    @staticmethod
    def _response_text(payload):
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
        raise ValueError("OpenAI response did not contain output text")

    def _request_translations(self, titles):
        response = requests.post(
            self._endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "instructions": (
                    "Translate every academic paper title into concise, accurate "
                    "Simplified Chinese. Preserve formulas, acronyms, model names, "
                    "and proper nouns. Return translations in exactly the same order."
                ),
                "input": json.dumps({"titles": titles}, ensure_ascii=False),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "paper_title_translations",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "translations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["translations"],
                            "additionalProperties": False,
                        },
                    },
                },
                "store": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        translations = json.loads(
            self._response_text(response.json())
        ).get("translations", [])
        if len(translations) != len(titles):
            raise ValueError("OpenAI returned an unexpected translation count")
        return [translation.strip() for translation in translations]

    def translate_many(self, titles):
        unique_titles = list(dict.fromkeys(title.strip() for title in titles if title))
        translated = {}
        missing = []

        for title in unique_titles:
            if self.contains_chinese(title):
                translated[title] = title
            elif self.cache.get(title):
                translated[title] = self.cache[title]
            else:
                missing.append(title)

        if missing and self.api_key:
            try:
                new_translations = self._request_translations(missing)
                for title, translation in zip(missing, new_translations):
                    if translation:
                        translated[title] = translation
                        self.cache[title] = translation
                self._save_cache()
            except (
                    requests.RequestException,
                    ValueError,
                    json.JSONDecodeError,
                    OSError,
            ) as exc:
                logger.warning(f"Title translation failed; continuing without it: {exc}")
        elif missing:
            logger.warning(
                "OPENAI_API_KEY is not configured; foreign titles will show as 未翻译."
            )

        for title in missing:
            translated.setdefault(title, "未翻译")
        return translated
