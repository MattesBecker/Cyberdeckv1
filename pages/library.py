from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from services import (
    LibraryDocument,
    LibraryEntry,
    LibraryService,
    LibraryServiceError,
)

from .base import BasePage

if TYPE_CHECKING:
    from display import EpaperDisplay


DirectoryState = Tuple[Path, List[LibraryEntry], int, int]


class LibraryPage(BasePage):
    key = "library"
    title = "LIBRARY"

    LIST_MODE = "list"
    FILE_MODE = "file"
    ERROR_MODE = "error"

    def __init__(self, service: LibraryService) -> None:
        self.service = service
        self.mode = self.LIST_MODE
        self.current_directory = Path()
        self.entries: List[LibraryEntry] = []
        self.selected_index = 0
        self.list_offset = 0
        self.current_document: Optional[LibraryDocument] = None
        self.page_index = 0
        self._row_count = 5
        self._wrapped_text: Optional[List[str]] = None
        self._history: List[DirectoryState] = []
        self._error_title = self.title
        self._error_message = ""

    def open_root(self) -> None:
        self.mode = self.LIST_MODE
        self.current_directory = Path()
        self.entries = []
        self.selected_index = 0
        self.list_offset = 0
        self.current_document = None
        self.page_index = 0
        self._wrapped_text = None
        self._history = []
        try:
            self.entries = self.service.list_directory()
        except LibraryServiceError as exc:
            self._show_error(self.title, str(exc))

    def move_up(self) -> bool:
        if self.mode == self.FILE_MODE:
            if self.page_index == 0:
                return False
            self.page_index -= 1
            return True
        if self.mode != self.LIST_MODE or len(self.entries) <= 1:
            return False
        self.selected_index = (self.selected_index - 1) % len(self.entries)
        return True

    def move_down(self) -> bool:
        if self.mode == self.FILE_MODE:
            page_count = self._page_count()
            if self.page_index + 1 >= page_count:
                return False
            self.page_index += 1
            return True
        if self.mode != self.LIST_MODE or len(self.entries) <= 1:
            return False
        self.selected_index = (self.selected_index + 1) % len(self.entries)
        return True

    def select(self) -> str:
        if self.mode != self.LIST_MODE or not self.entries:
            return "unchanged"

        entry = self.entries[self.selected_index]
        if entry.is_directory:
            try:
                entries = self.service.list_directory(entry.relative_path)
            except LibraryServiceError as exc:
                self._show_error(entry.name, str(exc))
                return "changed"
            self._history.append(
                (
                    self.current_directory,
                    self.entries,
                    self.selected_index,
                    self.list_offset,
                )
            )
            self.current_directory = entry.relative_path
            self.entries = entries
            self.selected_index = 0
            self.list_offset = 0
            return "changed"

        try:
            self.current_document = self.service.read_document(
                entry.relative_path
            )
        except LibraryServiceError as exc:
            self._show_error(entry.name, str(exc))
            return "changed"
        self.mode = self.FILE_MODE
        self.page_index = 0
        self._wrapped_text = None
        return "opened"

    def back(self) -> bool:
        if self.mode in (self.FILE_MODE, self.ERROR_MODE):
            self.mode = self.LIST_MODE
            self.current_document = None
            self.page_index = 0
            self._wrapped_text = None
            self._error_message = ""
            return True
        if not self._history:
            return False

        (
            self.current_directory,
            self.entries,
            self.selected_index,
            self.list_offset,
        ) = self._history.pop()
        return True

    def render(self, display: "EpaperDisplay") -> bool:
        if self.mode == self.FILE_MODE and self.current_document is not None:
            return self._render_document(display)
        if self.mode == self.ERROR_MODE:
            return self._render_error(display)
        return self._render_list(display)

    def _render_list(self, display: "EpaperDisplay") -> bool:
        self._row_count = display.body_line_count
        self._keep_selection_visible()
        end = min(self.list_offset + self._row_count, len(self.entries))
        lines = []
        for index in range(self.list_offset, end):
            entry = self.entries[index]
            label = entry.name + "/" if entry.is_directory else entry.name
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + label)

        if not lines:
            lines = ["(empty)"]
            footer = "b: back"
        else:
            footer = "{0}/{1}  w/s  Enter  b".format(
                self.selected_index + 1, len(self.entries)
            )
        return display.render_page(self._directory_title(), lines, footer)

    def _render_document(self, display: "EpaperDisplay") -> bool:
        document = self.current_document
        if document is None:
            return self._render_list(display)

        self._row_count = max(1, display.body_line_count)
        if self._wrapped_text is None:
            self._wrapped_text = display.wrap_text(document.text)
        page_count = self._page_count()
        self.page_index = min(self.page_index, page_count - 1)
        start = self.page_index * self._row_count
        end = start + self._row_count
        footer = "{0}/{1}  w/s  b".format(self.page_index + 1, page_count)
        return display.render_page(
            document.name, self._wrapped_text[start:end], footer
        )

    def _render_error(self, display: "EpaperDisplay") -> bool:
        lines = display.wrap_text(self._error_message)
        return display.render_page(
            self._error_title, lines[: display.body_line_count], "b: back"
        )

    def _show_error(self, title: str, message: str) -> None:
        self.mode = self.ERROR_MODE
        self.current_document = None
        self.page_index = 0
        self._wrapped_text = None
        self._error_title = title
        self._error_message = message

    def _keep_selection_visible(self) -> None:
        if not self.entries:
            self.selected_index = 0
            self.list_offset = 0
            return
        self.selected_index = min(self.selected_index, len(self.entries) - 1)
        if self.selected_index < self.list_offset:
            self.list_offset = self.selected_index
        elif self.selected_index >= self.list_offset + self._row_count:
            self.list_offset = self.selected_index - self._row_count + 1
        maximum = max(0, len(self.entries) - self._row_count)
        self.list_offset = min(self.list_offset, maximum)

    def _page_count(self) -> int:
        line_count = len(self._wrapped_text or [""])
        return max(1, (line_count + self._row_count - 1) // self._row_count)

    def _directory_title(self) -> str:
        if not self.current_directory.parts:
            return self.title
        return self.current_directory.name
