from typing import TYPE_CHECKING, List, Optional, Tuple

from library import (
    ITEM_TYPE_BACK,
    ITEM_TYPE_DIRECTORY,
    ITEM_TYPE_DOCUMENT,
    ITEM_TYPE_SEARCH,
    LibraryDocument,
    LibraryItem,
    LibraryProvider,
    LibraryProviderError,
    LibraryProviderRegistry,
    SearchResult,
)
from input_common import (
    EVENT_BACKSPACE,
    EVENT_CHARACTER,
    EVENT_ENTER,
    EVENT_EOF,
    EVENT_ESCAPE,
    EVENT_INVALID,
    EVENT_LEFT,
    EVENT_RIGHT,
    EVENT_SPECIAL,
    EVENT_TAB,
    EVENT_TEXT,
    InputEvent,
    command_for_event,
)

from .base import BasePage

if TYPE_CHECKING:
    from display import EpaperDisplay


DirectoryState = Tuple[str, str, List[LibraryItem], int, int]


class LibraryPage(BasePage):
    key = "library"
    title = "LIBRARY"

    MAIN_MODE = "main"
    BROWSE_MODE = "browse"
    DOCUMENT_MODE = "document"
    MESSAGE_MODE = "message"
    SEARCH_MODE = "search"
    RESULTS_MODE = "results"

    def __init__(self, providers: LibraryProviderRegistry) -> None:
        self.providers = providers
        self.mode = self.MAIN_MODE
        self.active_provider: Optional[LibraryProvider] = None
        self.current_container_id = ""
        self.current_container_title = self.title
        self.items: List[LibraryItem] = []
        self.selected_index = 0
        self.list_offset = 0
        self.current_document: Optional[LibraryDocument] = None
        self.search_provider: Optional[LibraryProvider] = None
        self.search_buffer = ""
        self.search_results: List[SearchResult] = []
        self.page_index = 0
        self._row_count = 5
        self._wrapped_text: Optional[List[str]] = None
        self._browse_history: List[DirectoryState] = []
        self._message_title = self.title
        self._message_text = ""
        self._message_return_mode = self.MAIN_MODE
        self._document_return_mode = self.BROWSE_MODE

    def open_library(self) -> None:
        """Open the provider menu without touching provider storage."""
        self.mode = self.MAIN_MODE
        self.active_provider = None
        self.current_container_id = ""
        self.current_container_title = self.title
        self.items = []
        self.selected_index = 0
        self.list_offset = 0
        self.current_document = None
        self.search_provider = None
        self.search_buffer = ""
        self.search_results = []
        self.page_index = 0
        self._wrapped_text = None
        self._browse_history = []
        self._message_text = ""

    def open_provider(self, provider_key: str) -> bool:
        """Open one provider root, reporting invalid providers on the page."""
        try:
            provider = self.providers.get(provider_key)
            items = provider.list_items("")
        except LibraryProviderError as exc:
            self._show_message(self.title, str(exc), self.MAIN_MODE)
            return False

        self.mode = self.BROWSE_MODE
        self.active_provider = provider
        self.current_container_id = ""
        self.current_container_title = provider.title
        self.items = items
        self.selected_index = 0
        self.list_offset = 0
        self.current_document = None
        self.search_provider = None
        self.search_buffer = ""
        self.search_results = []
        self.page_index = 0
        self._wrapped_text = None
        self._browse_history = []
        return True

    def move_up(self) -> bool:
        if self.mode == self.DOCUMENT_MODE:
            if self.page_index == 0:
                return False
            self.page_index -= 1
            return True
        item_count = self._selectable_count()
        if (
            self.mode not in (
                self.MAIN_MODE,
                self.BROWSE_MODE,
                self.RESULTS_MODE,
            )
            or item_count <= 1
        ):
            return False
        self.selected_index = (self.selected_index - 1) % item_count
        return True

    def move_down(self) -> bool:
        if self.mode == self.DOCUMENT_MODE:
            page_count = self._page_count()
            if self.page_index + 1 >= page_count:
                return False
            self.page_index += 1
            return True
        item_count = self._selectable_count()
        if (
            self.mode not in (
                self.MAIN_MODE,
                self.BROWSE_MODE,
                self.RESULTS_MODE,
            )
            or item_count <= 1
        ):
            return False
        self.selected_index = (self.selected_index + 1) % item_count
        return True

    def select(self) -> str:
        if self.mode == self.MAIN_MODE:
            return self._select_main_item()
        if self.mode == self.RESULTS_MODE:
            return self._open_selected_result()
        if self.mode != self.BROWSE_MODE or not self.items:
            return "unchanged"

        item = self.items[self.selected_index]
        provider = self.active_provider
        if provider is None or item.provider != provider.key:
            self._show_message(
                item.title,
                "Library item belongs to an unavailable provider.",
                self.BROWSE_MODE,
            )
            return "changed"

        if item.item_type == ITEM_TYPE_DIRECTORY:
            try:
                items = provider.list_items(item.id)
            except LibraryProviderError as exc:
                self._show_message(item.title, str(exc), self.BROWSE_MODE)
                return "changed"
            self._browse_history.append(
                (
                    self.current_container_id,
                    self.current_container_title,
                    self.items,
                    self.selected_index,
                    self.list_offset,
                )
            )
            self.current_container_id = item.id
            self.current_container_title = item.title
            self.items = items
            self.selected_index = 0
            self.list_offset = 0
            return "changed"

        if item.item_type == ITEM_TYPE_SEARCH:
            if not provider.supports_search:
                self._show_message(
                    item.title,
                    "Search is not available for this provider.",
                    self.BROWSE_MODE,
                )
                return "changed"
            self.search_provider = provider
            self.search_buffer = ""
            self.search_results = []
            self.selected_index = 0
            self.list_offset = 0
            self.mode = self.SEARCH_MODE
            return "changed"

        if item.item_type == ITEM_TYPE_BACK:
            self.back()
            return "changed"

        if item.item_type != ITEM_TYPE_DOCUMENT:
            self._show_message(
                item.title,
                "Unsupported library item type.",
                self.BROWSE_MODE,
            )
            return "changed"

        try:
            self.current_document = provider.open_item(item.id)
        except LibraryProviderError as exc:
            self._show_message(item.title, str(exc), self.BROWSE_MODE)
            return "changed"
        self.mode = self.DOCUMENT_MODE
        self._document_return_mode = self.BROWSE_MODE
        self.page_index = 0
        self._wrapped_text = None
        return "opened"

    def back(self) -> bool:
        if self.mode == self.DOCUMENT_MODE:
            self.mode = self._document_return_mode
            self.current_document = None
            self.page_index = 0
            self._wrapped_text = None
            return True
        if self.mode == self.RESULTS_MODE:
            self.mode = self.SEARCH_MODE
            self.selected_index = 0
            self.list_offset = 0
            return True
        if self.mode == self.SEARCH_MODE:
            self.mode = self.BROWSE_MODE
            self.search_results = []
            self.selected_index = 0
            self.list_offset = 0
            return True
        if self.mode == self.MESSAGE_MODE:
            self.mode = self._message_return_mode
            self._message_text = ""
            return True
        if self.mode == self.MAIN_MODE:
            return False
        if not self._browse_history:
            self.open_library()
            return True

        (
            self.current_container_id,
            self.current_container_title,
            self.items,
            self.selected_index,
            self.list_offset,
        ) = self._browse_history.pop()
        return True

    def render(self, display: "EpaperDisplay") -> bool:
        if self.mode == self.DOCUMENT_MODE and self.current_document is not None:
            return self._render_document(display)
        if self.mode == self.MESSAGE_MODE:
            return self._render_message(display)
        if self.mode == self.SEARCH_MODE:
            return self._render_search(display)
        if self.mode == self.RESULTS_MODE:
            return self._render_results(display)
        if self.mode == self.BROWSE_MODE:
            return self._render_items(display)
        return self._render_main(display)

    def handle_event(self, event: InputEvent) -> str:
        """Handle navigation and CardKB/CLI search text uniformly."""
        if self.mode == self.SEARCH_MODE:
            return self._handle_search_event(event)

        command = command_for_event(event)
        if command == "quit":
            return "quit"
        if command == "up":
            return "changed" if self.move_up() else "unchanged"
        if command == "down":
            return "changed" if self.move_down() else "unchanged"
        if command == "select":
            result = self.select()
            return "back" if result == "back" else result
        if command == "back":
            return "changed" if self.back() else "back"
        return "invalid"

    def _render_main(self, display: "EpaperDisplay") -> bool:
        labels = self._main_labels()
        self._row_count = display.body_line_count
        self._keep_selection_visible(len(labels))
        end = min(self.list_offset + self._row_count, len(labels))
        lines = []
        for index in range(self.list_offset, end):
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + labels[index])
        footer = "{0}/{1}  w/s  Enter  b".format(
            self.selected_index + 1, len(labels)
        )
        return display.render_page(self.title, lines, footer)

    def _render_items(self, display: "EpaperDisplay") -> bool:
        self._row_count = display.body_line_count
        self._keep_selection_visible(len(self.items))
        end = min(self.list_offset + self._row_count, len(self.items))
        lines = []
        for index in range(self.list_offset, end):
            item = self.items[index]
            label = (
                item.title + "/"
                if item.item_type == ITEM_TYPE_DIRECTORY
                else item.title
            )
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + label)
        if not lines:
            lines = ["(empty)"]
            footer = "b: back"
        else:
            footer = "{0}/{1}  w/s  Enter  b".format(
                self.selected_index + 1, len(self.items)
            )
        return display.render_page(self.current_container_title, lines, footer)

    def _render_search(self, display: "EpaperDisplay") -> bool:
        provider = self.search_provider
        title = provider.search_title if provider is not None else "SEARCH"
        lines = display.wrap_text("> " + self.search_buffer + "_")
        return display.render_page(
            title,
            lines[-display.body_line_count :],
            "Enter: search  Esc: back",
        )

    def _render_results(self, display: "EpaperDisplay") -> bool:
        self._row_count = display.body_line_count
        self._keep_selection_visible(len(self.search_results))
        end = min(
            self.list_offset + self._row_count, len(self.search_results)
        )
        lines = []
        for index in range(self.list_offset, end):
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + self.search_results[index].title)
        footer = "{0}/{1}  w/s  Enter  b".format(
            self.selected_index + 1, len(self.search_results)
        )
        return display.render_page("RESULTS", lines, footer)

    def _render_document(self, display: "EpaperDisplay") -> bool:
        document = self.current_document
        if document is None:
            return self._render_items(display)

        self._row_count = max(1, display.body_line_count)
        if self._wrapped_text is None:
            self._wrapped_text = display.wrap_text(document.text)
        page_count = self._page_count()
        self.page_index = min(self.page_index, page_count - 1)
        start = self.page_index * self._row_count
        end = start + self._row_count
        footer = "{0}/{1}  w/s  b".format(self.page_index + 1, page_count)
        return display.render_page(
            document.title, self._wrapped_text[start:end], footer
        )

    def _render_message(self, display: "EpaperDisplay") -> bool:
        lines = display.wrap_text(self._message_text)
        return display.render_page(
            self._message_title, lines[: display.body_line_count], "b: back"
        )

    def _show_message(self, title: str, text: str, return_mode: str) -> None:
        self.mode = self.MESSAGE_MODE
        self.current_document = None
        self.page_index = 0
        self._wrapped_text = None
        self._message_title = title
        self._message_text = text
        self._message_return_mode = return_mode

    def _handle_search_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if event.kind in (EVENT_ESCAPE, EVENT_LEFT):
            self.back()
            return "changed"
        if event.kind == EVENT_CHARACTER and event.character is not None:
            self.search_buffer += event.character
            return "changed"
        if event.kind == EVENT_TEXT and event.character is not None:
            self.search_buffer = event.character
            return "changed" if self._run_search() else "unchanged"
        if event.kind == EVENT_TAB:
            self.search_buffer += " "
            return "changed"
        if event.kind == EVENT_BACKSPACE:
            if not self.search_buffer:
                self.back()
                return "changed"
            self.search_buffer = self.search_buffer[:-1]
            return "changed"
        if event.kind in (EVENT_ENTER, EVENT_RIGHT):
            return "changed" if self._run_search() else "unchanged"
        if event.kind in (EVENT_INVALID, EVENT_SPECIAL):
            return "invalid"
        return "unchanged"

    def _run_search(self) -> bool:
        provider = self.search_provider
        query = self.search_buffer.strip()
        if provider is None or not query:
            self._show_message(
                "SEARCH",
                "Enter a search term.",
                self.SEARCH_MODE,
            )
            return True
        try:
            results = provider.search(query)
        except LibraryProviderError as exc:
            self._show_message(provider.title, str(exc), self.SEARCH_MODE)
            return True
        if not results:
            self._show_message("RESULTS", "No results", self.SEARCH_MODE)
            return True
        self.search_results = results
        self.mode = self.RESULTS_MODE
        self.selected_index = 0
        self.list_offset = 0
        return True

    def _open_selected_result(self) -> str:
        if not self.search_results:
            return "unchanged"
        result = self.search_results[self.selected_index]
        try:
            provider = self.providers.get(result.provider)
            document = provider.open_item(result.id)
        except LibraryProviderError as exc:
            self._show_message(
                result.title,
                str(exc),
                self.RESULTS_MODE,
            )
            return "changed"
        self.active_provider = provider
        self.current_document = document
        self.mode = self.DOCUMENT_MODE
        self._document_return_mode = self.RESULTS_MODE
        self.page_index = 0
        self._wrapped_text = None
        return "opened"

    def _select_main_item(self) -> str:
        providers = self.providers.list_providers()
        if self.selected_index < len(providers):
            self.open_provider(providers[self.selected_index].key)
            return "changed"
        if self.selected_index == len(providers):
            self._show_message(
                "SEARCH",
                "Search is not available in this version.",
                self.MAIN_MODE,
            )
            return "changed"
        return "back"

    def _main_labels(self) -> List[str]:
        labels = [provider.title for provider in self.providers.list_providers()]
        labels.extend(("Search", "Back"))
        return labels

    def _selectable_count(self) -> int:
        if self.mode == self.MAIN_MODE:
            return len(self._main_labels())
        if self.mode == self.BROWSE_MODE:
            return len(self.items)
        if self.mode == self.RESULTS_MODE:
            return len(self.search_results)
        return 0

    def _keep_selection_visible(self, item_count: int) -> None:
        if not item_count:
            self.selected_index = 0
            self.list_offset = 0
            return
        self.selected_index = min(self.selected_index, item_count - 1)
        if self.selected_index < self.list_offset:
            self.list_offset = self.selected_index
        elif self.selected_index >= self.list_offset + self._row_count:
            self.list_offset = self.selected_index - self._row_count + 1
        maximum = max(0, item_count - self._row_count)
        self.list_offset = min(self.list_offset, maximum)

    def _page_count(self) -> int:
        line_count = len(self._wrapped_text or [""])
        return max(1, (line_count + self._row_count - 1) // self._row_count)
