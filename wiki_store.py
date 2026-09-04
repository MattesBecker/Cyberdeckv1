from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from json_store import JSONStoreError, load_json, save_json


class WikiStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class WikiBookmark:
    provider: str
    article_id: str
    title: str
    created_at: str


@dataclass(frozen=True)
class WikiHistoryEntry:
    provider: str
    article_id: str
    title: str
    opened_at: str


class WikiBookmarksStore:
    def __init__(
        self,
        path: Path,
        limit: int = 200,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.path = Path(path)
        self.limit = max(1, int(limit))
        self._clock = clock

    def list(self) -> List[WikiBookmark]:
        raw = load_json(self.path, [])
        if not isinstance(raw, list):
            return []
        result = []
        seen = set()
        for value in raw:
            item = _parse_bookmark(value)
            key = None if item is None else (item.provider, item.article_id)
            if item is not None and key not in seen:
                result.append(item)
                seen.add(key)
        return result[: self.limit]

    def contains(self, provider: str, article_id: str) -> bool:
        return any(
            item.provider == provider and item.article_id == article_id
            for item in self.list()
        )

    def toggle(self, provider: str, article_id: str, title: str) -> bool:
        _validate_article(provider, article_id, title)
        items = self.list()
        remaining = [
            item for item in items
            if (item.provider, item.article_id) != (provider, article_id)
        ]
        added = len(remaining) == len(items)
        if added:
            remaining.insert(
                0,
                WikiBookmark(
                    provider,
                    article_id,
                    _clean_title(title),
                    self._clock().replace(microsecond=0).isoformat(),
                ),
            )
        self._save(remaining[: self.limit])
        return added

    def remove(self, provider: str, article_id: str) -> bool:
        items = self.list()
        remaining = [
            item for item in items
            if (item.provider, item.article_id) != (provider, article_id)
        ]
        if len(items) == len(remaining):
            return False
        self._save(remaining)
        return True

    def _save(self, items: List[WikiBookmark]) -> None:
        try:
            save_json(self.path, [asdict(item) for item in items])
        except JSONStoreError as exc:
            raise WikiStoreError(str(exc)) from exc


class WikiHistoryStore:
    def __init__(
        self,
        path: Path,
        limit: int = 50,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.path = Path(path)
        self.limit = max(1, int(limit))
        self._clock = clock

    def list(self) -> List[WikiHistoryEntry]:
        raw = load_json(self.path, [])
        if not isinstance(raw, list):
            return []
        result = []
        seen = set()
        for value in raw:
            item = _parse_history(value)
            key = None if item is None else (item.provider, item.article_id)
            if item is not None and key not in seen:
                result.append(item)
                seen.add(key)
        return result[: self.limit]

    def record(self, provider: str, article_id: str, title: str) -> None:
        _validate_article(provider, article_id, title)
        items = [
            item for item in self.list()
            if (item.provider, item.article_id) != (provider, article_id)
        ]
        items.insert(
            0,
            WikiHistoryEntry(
                provider,
                article_id,
                _clean_title(title),
                self._clock().replace(microsecond=0).isoformat(),
            ),
        )
        self._save(items[: self.limit])

    def remove(self, provider: str, article_id: str) -> bool:
        items = self.list()
        remaining = [
            item for item in items
            if (item.provider, item.article_id) != (provider, article_id)
        ]
        if len(items) == len(remaining):
            return False
        self._save(remaining)
        return True

    def clear(self) -> None:
        self._save([])

    def _save(self, items: List[WikiHistoryEntry]) -> None:
        try:
            save_json(self.path, [asdict(item) for item in items])
        except JSONStoreError as exc:
            raise WikiStoreError(str(exc)) from exc


def _clean_title(title: str) -> str:
    return " ".join(title.splitlines()).strip()


def _validate_article(provider: str, article_id: str, title: str) -> None:
    if not all(isinstance(value, str) for value in (provider, article_id, title)):
        raise WikiStoreError("Invalid Wikipedia entry.")
    if not provider.strip() or not article_id.startswith("/content/") or not _clean_title(title):
        raise WikiStoreError("Invalid Wikipedia entry.")


def _parse_bookmark(value) -> Optional[WikiBookmark]:
    if not isinstance(value, dict):
        return None
    fields = tuple(value.get(key) for key in ("provider", "article_id", "title", "created_at"))
    if not all(isinstance(field, str) and field.strip() for field in fields):
        return None
    if not fields[1].startswith("/content/"):
        return None
    return WikiBookmark(fields[0], fields[1], _clean_title(fields[2]), fields[3])


def _parse_history(value) -> Optional[WikiHistoryEntry]:
    if not isinstance(value, dict):
        return None
    fields = tuple(value.get(key) for key in ("provider", "article_id", "title", "opened_at"))
    if not all(isinstance(field, str) and field.strip() for field in fields):
        return None
    if not fields[1].startswith("/content/"):
        return None
    return WikiHistoryEntry(fields[0], fields[1], _clean_title(fields[2]), fields[3])
