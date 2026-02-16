"""JSON-based cache for product descriptions."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path("cache/descriptions_cache.json")


class DescriptionCache:
    """Persistent cache: article -> description string."""

    def __init__(self, cache_path: Path = DEFAULT_CACHE_PATH):
        self.cache_path = cache_path
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.cache_path.exists():
            with open(self.cache_path, encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info("Loaded %d cached descriptions from %s", len(self._data), self.cache_path)

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def put(self, key: str, description: str) -> None:
        self._data[key] = description

    def has(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)
