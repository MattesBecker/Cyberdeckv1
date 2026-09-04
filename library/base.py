from dataclasses import dataclass
from typing import List, Mapping, Optional


ITEM_TYPE_DIRECTORY = "directory"
ITEM_TYPE_DOCUMENT = "document"
ITEM_TYPE_SEARCH = "search"
ITEM_TYPE_BACK = "back"
ITEM_TYPE_BOOKMARKS = "bookmarks"
ITEM_TYPE_HISTORY = "history"


class LibraryProviderError(RuntimeError):
    """Raised when a provider or library item cannot be used safely."""


@dataclass(frozen=True)
class LibraryItem:
    provider: str
    id: str
    title: str
    item_type: str
    metadata: Optional[Mapping[str, str]] = None


@dataclass(frozen=True)
class LibraryDocument:
    provider: str
    id: str
    title: str
    text: str
    source: Optional[str] = None
    metadata: Optional[Mapping[str, str]] = None


@dataclass(frozen=True)
class SearchResult:
    provider: str
    id: str
    title: str
    preview: str
    metadata: Optional[Mapping[str, str]] = None


class LibraryProvider:
    """Small provider contract shared by local files and future sources."""

    key = ""
    title = ""
    supports_search = False
    search_title = "SEARCH"

    def list_items(self, container_id: str = "") -> List[LibraryItem]:
        raise NotImplementedError

    def search(self, query: str) -> List[SearchResult]:
        raise LibraryProviderError(
            "Search is not supported by provider '{0}'.".format(self.key)
        )

    def open_item(self, item_id: str) -> LibraryDocument:
        raise NotImplementedError

    def get_title(self, item_id: str) -> str:
        raise NotImplementedError

    def close(self) -> None:
        """Release resources owned by this provider, if any."""
        pass
