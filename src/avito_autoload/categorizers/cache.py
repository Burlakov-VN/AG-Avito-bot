"""JSON-based cache for category classification results."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path("cache/categories_cache.json")


class CategoryCache:
    """Persistent cache: article -> category result."""

    def __init__(self, cache_path: Path = DEFAULT_CACHE_PATH):
        self.cache_path = cache_path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_path.exists():
            with open(self.cache_path, encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info("Loaded %d cached categories from %s", len(self._data), self.cache_path)

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, article: str) -> dict | None:
        return self._data.get(article)

    def put(self, article: str, result: dict) -> None:
        self._data[article] = result

    def has(self, article: str) -> bool:
        return article in self._data

    def __len__(self) -> int:
        return len(self._data)
