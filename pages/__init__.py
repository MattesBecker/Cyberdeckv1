from typing import Dict

from notes_store import NotesStore

from .base import BasePage
from .library import LibraryPage
from .notes import NotesPage
from .sync import SyncPage
from .tasks import TasksPage
from .terminal import TerminalPage
from .tools import ToolsPage


STATIC_PAGE_TYPES = (
    TasksPage,
    TerminalPage,
    LibraryPage,
    ToolsPage,
    SyncPage,
)


def create_pages(notes_store: NotesStore) -> Dict[str, BasePage]:
    pages = {
        page_type.key: page_type() for page_type in STATIC_PAGE_TYPES
    }
    pages[NotesPage.key] = NotesPage(notes_store)
    return pages


__all__ = ["BasePage", "create_pages"]
