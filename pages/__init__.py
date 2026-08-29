from typing import Dict

from .base import BasePage
from .library import LibraryPage
from .notes import NotesPage
from .sync import SyncPage
from .tasks import TasksPage
from .terminal import TerminalPage
from .tools import ToolsPage


PAGE_TYPES = (
    NotesPage,
    TasksPage,
    TerminalPage,
    LibraryPage,
    ToolsPage,
    SyncPage,
)


def create_pages() -> Dict[str, BasePage]:
    return {page_type.key: page_type() for page_type in PAGE_TYPES}


__all__ = ["BasePage", "create_pages"]
