from typing import Dict, Optional

from notes_store import NotesStore
from services import LibraryService, NetworkInfoService, SystemInfoService
from tasks_store import TasksStore

from .base import BasePage
from .library import LibraryPage
from .notes import NotesPage
from .sync import SyncPage
from .tasks import TasksPage
from .terminal import TerminalPage
from .tools import ToolsPage


STATIC_PAGE_TYPES = (
    TerminalPage,
    SyncPage,
)


def create_pages(
    notes_store: NotesStore,
    tasks_store: TasksStore,
    library_service: LibraryService,
    system_service: Optional[SystemInfoService] = None,
    network_service: Optional[NetworkInfoService] = None,
) -> Dict[str, BasePage]:
    pages = {
        page_type.key: page_type() for page_type in STATIC_PAGE_TYPES
    }
    pages[NotesPage.key] = NotesPage(notes_store)
    pages[TasksPage.key] = TasksPage(tasks_store)
    pages[LibraryPage.key] = LibraryPage(library_service)
    pages[ToolsPage.key] = ToolsPage(
        system_service or SystemInfoService(),
        network_service or NetworkInfoService(),
    )
    return pages


__all__ = ["BasePage", "create_pages"]
