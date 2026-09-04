from pathlib import Path
from typing import List, Optional

from input_common import EVENT_EOF, EVENT_ESCAPE, InputEvent, command_for_event
from services import FileEntry, FileViewerError, FileViewerService, TextFile


class FileViewerPage:
    ROOTS_MODE = "roots"
    BROWSE_MODE = "browse"
    DOCUMENT_MODE = "document"
    MESSAGE_MODE = "message"

    def __init__(self, service: FileViewerService) -> None:
        self.service = service
        self.mode = self.ROOTS_MODE
        self.entries: List[FileEntry] = []
        self.current_dir: Optional[Path] = None
        self.current_root: Optional[Path] = None
        self.document: Optional[TextFile] = None
        self.selected_index = 0
        self.list_offset = 0
        self.page_index = 0
        self._wrapped = None
        self._row_count = 5
        self.message = ""

    def open(self) -> None:
        self.mode = self.ROOTS_MODE
        self.entries = self.service.available_roots()
        self.current_dir = None
        self.current_root = None
        self.document = None
        self.selected_index = 0
        self.list_offset = 0
        self.message = ""

    def handle_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        command = command_for_event(event)
        if self.mode == self.DOCUMENT_MODE:
            if command == "up" and self.page_index > 0:
                self.page_index -= 1
                return "changed"
            if command == "down" and self.page_index + 1 < self._page_count():
                self.page_index += 1
                return "changed"
            if command == "back" or event.kind == EVENT_ESCAPE:
                self.mode = self.BROWSE_MODE
                self.document = None
                self._wrapped = None
                return "changed"
            return "unchanged"
        if self.mode == self.MESSAGE_MODE:
            if command == "back" or command == "select":
                self.mode = self.BROWSE_MODE if self.current_dir else self.ROOTS_MODE
                return "changed"
            return "unchanged"
        count = len(self.entries) + 1
        if command == "up":
            self.selected_index = (self.selected_index - 1) % count
            return "changed"
        if command == "down":
            self.selected_index = (self.selected_index + 1) % count
            return "changed"
        if command == "back":
            return self._back()
        if command != "select":
            return "invalid"
        if self.selected_index == len(self.entries):
            return self._back()
        entry = self.entries[self.selected_index]
        if entry.is_directory:
            return self._open_directory(entry.path)
        return self._open_file(entry.path)

    def render(self, display) -> bool:
        self._row_count = display.body_line_count
        if self.mode == self.DOCUMENT_MODE and self.document is not None:
            if self._wrapped is None:
                self._wrapped = display.wrap_text(self.document.text)
            pages = self._page_count()
            self.page_index = min(self.page_index, pages - 1)
            start = self.page_index * self._row_count
            return display.render_page(
                self.document.title,
                self._wrapped[start:start + self._row_count],
                "{0}/{1} w/s b".format(self.page_index + 1, pages),
            )
        if self.mode == self.MESSAGE_MODE:
            return display.render_page("FILE VIEWER", display.wrap_text(self.message)[:self._row_count], "b: back")
        labels = [entry.title for entry in self.entries] + (["Back"] if self.mode == self.ROOTS_MODE else [".."])
        self._keep_visible(len(labels))
        end = min(self.list_offset + self._row_count, len(labels))
        lines = [("> " if index == self.selected_index else "  ") + labels[index] for index in range(self.list_offset, end)]
        title = "FILE ROOTS" if self.mode == self.ROOTS_MODE else (self.current_dir.name or str(self.current_dir))
        return display.render_page(title, lines, "{0}/{1} Enter b".format(self.selected_index + 1, len(labels)))

    def _open_directory(self, path: Path) -> str:
        try:
            self.entries = self.service.list_directory(path)
            self.current_dir = Path(path).resolve()
            self.current_root = self.service.root_for(path)
            self.mode = self.BROWSE_MODE
            self.selected_index = 0
            self.list_offset = 0
            return "changed"
        except FileViewerError as exc:
            self.message = str(exc)
            self.mode = self.MESSAGE_MODE
            return "changed"

    def _open_file(self, path: Path) -> str:
        try:
            self.document = self.service.open_text(path)
            self.mode = self.DOCUMENT_MODE
            self.page_index = 0
            self._wrapped = None
            return "changed"
        except FileViewerError as exc:
            self.message = str(exc)
            self.mode = self.MESSAGE_MODE
            return "changed"

    def _back(self) -> str:
        if self.mode == self.ROOTS_MODE:
            return "back"
        if self.current_dir is None or self.current_root is None or self.current_dir == self.current_root:
            self.open()
            return "changed"
        return self._open_directory(self.current_dir.parent)

    def _page_count(self) -> int:
        return max(1, (len(self._wrapped or [""]) + self._row_count - 1) // self._row_count)

    def _keep_visible(self, count: int) -> None:
        self.selected_index = min(self.selected_index, max(0, count - 1))
        if self.selected_index < self.list_offset:
            self.list_offset = self.selected_index
        elif self.selected_index >= self.list_offset + self._row_count:
            self.list_offset = self.selected_index - self._row_count + 1
        self.list_offset = min(self.list_offset, max(0, count - self._row_count))
