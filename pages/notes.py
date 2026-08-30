from typing import TYPE_CHECKING, List, Optional

from notes_store import Note, NotesStore

from .base import BasePage

if TYPE_CHECKING:
    from display import EpaperDisplay


class NotesPage(BasePage):
    key = "notes"
    title = "NOTES"

    LIST_MODE = "list"
    NOTE_MODE = "note"

    def __init__(self, store: NotesStore) -> None:
        self.store = store
        self.notes: List[Note] = []
        self.selected_index = 0
        self.list_offset = 0
        self.mode = self.LIST_MODE
        self.current_note: Optional[Note] = None
        self.page_index = 0
        self._row_count = 5
        self._text_row_count = 4
        self._wrapped_text: List[str] = []
        self.reload()

    def open_list(self, reset_selection: bool = True) -> None:
        self.mode = self.LIST_MODE
        self.current_note = None
        self.page_index = 0
        self._wrapped_text = []
        self.reload()
        if reset_selection:
            self.selected_index = 0
            self.list_offset = 0

    def reload(self, preferred_filename: Optional[str] = None) -> None:
        old_index = self.selected_index
        self.notes = self.store.list_notes()
        if preferred_filename:
            for index, note in enumerate(self.notes):
                if note.filename == preferred_filename:
                    self.selected_index = index + 1
                    break
            else:
                self.selected_index = min(old_index, len(self.notes))
        else:
            self.selected_index = min(old_index, len(self.notes))
        self._keep_selection_visible(self._row_count)

    def move_up(self) -> bool:
        if self.mode == self.NOTE_MODE:
            if self.page_index == 0:
                return False
            self.page_index -= 1
            return True

        item_count = len(self.notes) + 1
        if item_count == 1:
            return False
        self.selected_index = (self.selected_index - 1) % item_count
        return True

    def move_down(self) -> bool:
        if self.mode == self.NOTE_MODE:
            page_count = self._page_count(self._text_row_count)
            if self.page_index + 1 >= page_count:
                return False
            self.page_index += 1
            return True

        item_count = len(self.notes) + 1
        if item_count == 1:
            return False
        self.selected_index = (self.selected_index + 1) % item_count
        return True

    def select(self) -> str:
        if self.mode == self.NOTE_MODE:
            return "unchanged"
        if self.selected_index == 0:
            return "new"

        selected_note = self.notes[self.selected_index - 1]
        self.current_note = self.store.load_note(selected_note.filename)
        if self.current_note is None:
            self.reload()
            return "changed"
        self.mode = self.NOTE_MODE
        self.page_index = 0
        self._wrapped_text = []
        return "opened"

    def add_note(self, title: str, text: str) -> None:
        note = self.store.create_note(title, text)
        self.mode = self.LIST_MODE
        self.current_note = None
        self.reload(preferred_filename=note.filename)

    def delete_current_note(self) -> bool:
        if self.mode != self.NOTE_MODE or self.current_note is None:
            return False
        old_index = self.selected_index
        self.store.delete_note(self.current_note)
        self.mode = self.LIST_MODE
        self.current_note = None
        self.page_index = 0
        self._wrapped_text = []
        self.notes = self.store.list_notes()
        self.selected_index = min(old_index, len(self.notes))
        return True

    def back_to_list(self) -> bool:
        if self.mode != self.NOTE_MODE:
            return False
        preferred = self.current_note.filename if self.current_note else None
        self.mode = self.LIST_MODE
        self.current_note = None
        self.page_index = 0
        self._wrapped_text = []
        self.reload(preferred_filename=preferred)
        return True

    def render(self, display: "EpaperDisplay") -> bool:
        if self.mode == self.NOTE_MODE and self.current_note is not None:
            return self._render_note(display)
        return self._render_list(display)

    def _render_list(self, display: "EpaperDisplay") -> bool:
        self._row_count = display.body_line_count
        self._keep_selection_visible(self._row_count)
        labels = ["+ New note"] + [note.title for note in self.notes]
        end = min(self.list_offset + self._row_count, len(labels))
        lines = []
        for index in range(self.list_offset, end):
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + labels[index])

        footer = "{0}/{1}  w/s  Enter  b".format(
            self.selected_index + 1, len(labels)
        )
        return display.render_page(self.title, lines, footer)

    def _render_note(self, display: "EpaperDisplay") -> bool:
        note = self.current_note
        if note is None:
            return self._render_list(display)

        self._text_row_count = max(1, display.body_line_count - 1)
        self._wrapped_text = display.wrap_text(note.text or "(empty note)")
        page_count = self._page_count(self._text_row_count)
        self.page_index = min(self.page_index, page_count - 1)
        start = self.page_index * self._text_row_count
        end = start + self._text_row_count
        lines = [note.title] + self._wrapped_text[start:end]
        footer = "{0}/{1}  w/s  d:del  b".format(
            self.page_index + 1, page_count
        )
        return display.render_page(self.title, lines, footer)

    def _keep_selection_visible(self, row_count: int) -> None:
        if self.selected_index < self.list_offset:
            self.list_offset = self.selected_index
        elif self.selected_index >= self.list_offset + row_count:
            self.list_offset = self.selected_index - row_count + 1
        maximum = max(0, len(self.notes) + 1 - row_count)
        self.list_offset = min(self.list_offset, maximum)

    def _page_count(self, row_count: int) -> int:
        return max(1, (len(self._wrapped_text) + row_count - 1) // row_count)
