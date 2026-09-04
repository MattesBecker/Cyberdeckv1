from typing import Callable, Dict, Optional

from config import (
    GAME_STATS_FILE,
    SETTINGS_FILE,
    WIKI_BOOKMARKS_FILE,
    WIKI_BOOKMARKS_LIMIT,
    WIKI_HISTORY_FILE,
    WIKI_HISTORY_LIMIT,
)
from game_logic import GameStatsStore

from library import LibraryProviderRegistry
from notes_store import NotesStore
from services import (
    NetworkInfoService,
    SystemInfoService,
    TerminalService,
)
from tasks_store import TasksStore
from terminal_history import TerminalHistoryStore
from settings_store import RuntimeSettings, SettingsStore
from wiki_store import WikiBookmarksStore, WikiHistoryStore

from .base import BasePage
from .dashboard import DashboardPage
from .games import GamesPage
from .library import LibraryPage
from .notes import NotesPage
from .settings import SettingsPage
from .tasks import TasksPage
from .terminal import TerminalPage
from .tools import ToolsPage


def create_pages(
    notes_store: NotesStore,
    tasks_store: TasksStore,
    library_providers: LibraryProviderRegistry,
    terminal_service: TerminalService,
    terminal_history: TerminalHistoryStore,
    system_service: Optional[SystemInfoService] = None,
    network_service: Optional[NetworkInfoService] = None,
    settings_store: Optional[SettingsStore] = None,
    runtime_settings: Optional[RuntimeSettings] = None,
    wiki_ready: Callable[[], bool] = lambda: False,
    bookmarks_store: Optional[WikiBookmarksStore] = None,
    history_store: Optional[WikiHistoryStore] = None,
    game_stats_store: Optional[GameStatsStore] = None,
) -> Dict[str, BasePage]:
    system = system_service or SystemInfoService()
    network = network_service or NetworkInfoService()
    settings_backend = settings_store or SettingsStore(SETTINGS_FILE)
    settings = runtime_settings or settings_backend.load()
    bookmarks = bookmarks_store or WikiBookmarksStore(WIKI_BOOKMARKS_FILE, WIKI_BOOKMARKS_LIMIT)
    history = history_store or WikiHistoryStore(WIKI_HISTORY_FILE, WIKI_HISTORY_LIMIT)
    pages = {}
    pages[NotesPage.key] = NotesPage(notes_store)
    pages[TasksPage.key] = TasksPage(tasks_store)
    pages[LibraryPage.key] = LibraryPage(library_providers, bookmarks, history)
    pages[TerminalPage.key] = TerminalPage(
        terminal_service, terminal_history
    )
    pages[ToolsPage.key] = ToolsPage(
        system,
        network,
    )
    pages[GamesPage.key] = GamesPage(game_stats_store or GameStatsStore(GAME_STATS_FILE))
    pages[SettingsPage.key] = SettingsPage(settings_backend, settings)
    pages[DashboardPage.key] = DashboardPage(
        tasks_store, network, system, settings, wiki_ready=wiki_ready
    )
    return pages


__all__ = ["BasePage", "create_pages"]
