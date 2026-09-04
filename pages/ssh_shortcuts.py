from typing import List, Optional

from input_common import (
    EVENT_BACKSPACE, EVENT_CHARACTER, EVENT_DOWN, EVENT_ENTER, EVENT_EOF,
    EVENT_ESCAPE, EVENT_LEFT, EVENT_RIGHT, EVENT_TAB, EVENT_TEXT, EVENT_UP,
    InputEvent,
)
from services import (
    SSHResult, SSHShortcut, SSHShortcutError, SSHShortcutService,
    SSHShortcutStore,
)


class SSHShortcutsPage:
    LIST_MODE = "list"
    FORM_MODE = "form"
    OUTPUT_MODE = "output"
    DELETE_MODE = "delete"
    FIELDS = ("name", "host", "user", "port", "command")

    def __init__(self, store: SSHShortcutStore, service: SSHShortcutService) -> None:
        self.store = store
        self.service = service
        self.mode = self.LIST_MODE
        self.shortcuts: List[SSHShortcut] = []
        self.selected_index = 0
        self.list_offset = 0
        self.field_index = 0
        self.form = {}
        self.edit_index: Optional[int] = None
        self.result: Optional[SSHResult] = None
        self.page_index = 0
        self._wrapped = None
        self._row_count = 5
        self.message = ""

    def open(self) -> None:
        self.shortcuts = self.store.list()
        self.mode = self.LIST_MODE
        self.selected_index = 0
        self.list_offset = 0
        self.message = ""

    def handle_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if self.mode == self.FORM_MODE:
            return self._handle_form(event)
        if self.mode == self.OUTPUT_MODE:
            if event.kind == EVENT_UP and self.page_index > 0:
                self.page_index -= 1
                return "changed"
            if event.kind == EVENT_DOWN and self.page_index + 1 < self._page_count():
                self.page_index += 1
                return "changed"
            if event.kind in (EVENT_ESCAPE, EVENT_LEFT):
                self.mode = self.LIST_MODE
                return "changed"
            return "unchanged"
        if self.mode == self.DELETE_MODE:
            value = (event.character or "").lower()
            if event.kind in (EVENT_ESCAPE, EVENT_LEFT) or value == "n":
                self.mode = self.LIST_MODE
                return "changed"
            if value == "y":
                try:
                    self.store.delete(self.selected_index)
                    self.shortcuts = self.store.list()
                    self.selected_index = min(self.selected_index, len(self.shortcuts))
                    self.message = "Deleted"
                except SSHShortcutError:
                    self.message = "Delete failed"
                self.mode = self.LIST_MODE
                return "changed"
            return "unchanged"
        if event.kind == EVENT_ESCAPE:
            return "back"
        if event.kind == EVENT_UP:
            self.selected_index = (self.selected_index - 1) % (len(self.shortcuts) + 2)
            return "changed"
        if event.kind == EVENT_DOWN:
            self.selected_index = (self.selected_index + 1) % (len(self.shortcuts) + 2)
            return "changed"
        text = (event.character or "").lower() if event.kind in (EVENT_CHARACTER, EVENT_TEXT) else ""
        if text == "d" and self.selected_index < len(self.shortcuts):
            self.mode = self.DELETE_MODE
            return "changed"
        if text == "e" and self.selected_index < len(self.shortcuts):
            self._open_form(self.selected_index)
            return "changed"
        if event.kind in (EVENT_ENTER, EVENT_RIGHT):
            if self.selected_index < len(self.shortcuts):
                shortcut = self.shortcuts[self.selected_index]
                self.result = self.service.run(shortcut)
                self.mode = self.OUTPUT_MODE
                self.page_index = 0
                self._wrapped = None
                return "changed"
            if self.selected_index == len(self.shortcuts):
                self._open_form(None)
                return "changed"
            return "back"
        return "invalid"

    def render(self, display) -> bool:
        self._row_count = display.body_line_count
        if self.mode == self.FORM_MODE:
            field = self.FIELDS[self.field_index]
            value = self.form.get(field, "")
            lines = display.wrap_text("> " + value + "_")
            return display.render_page(
                "SSH " + field.upper(),
                lines[-self._row_count:],
                self.message or "Enter:next Esc:cancel",
            )
        if self.mode == self.OUTPUT_MODE and self.result is not None:
            if self._wrapped is None:
                self._wrapped = display.wrap_text(self.result.output)
            pages = self._page_count()
            start = self.page_index * self._row_count
            title = "SSH OK" if self.result.success else "SSH ERROR"
            return display.render_page(title, self._wrapped[start:start + self._row_count], "{0}/{1} w/s b".format(self.page_index + 1, pages))
        if self.mode == self.DELETE_MODE:
            return display.render_page("DELETE SSH", ["Delete shortcut?", "y / n"], "Esc:cancel")
        labels = ["{0} - {1}".format(item.name, item.command) for item in self.shortcuts]
        labels.extend(("+ New shortcut", "Back"))
        self._keep_visible(len(labels))
        end = min(self.list_offset + self._row_count, len(labels))
        lines = [("> " if index == self.selected_index else "  ") + labels[index] for index in range(self.list_offset, end)]
        return display.render_page("SSH SHORTCUTS", lines, self.message or "Enter e d b")

    def _open_form(self, index: Optional[int]) -> None:
        self.mode = self.FORM_MODE
        self.field_index = 0
        self.edit_index = index
        self.message = ""
        if index is None:
            self.form = {"name": "", "host": "", "user": "", "port": "22", "command": ""}
        else:
            item = self.shortcuts[index]
            self.form = {"name": item.name, "host": item.host, "user": item.user, "port": str(item.port), "command": item.command}

    def _handle_form(self, event: InputEvent) -> str:
        if event.kind == EVENT_ESCAPE:
            self.mode = self.LIST_MODE
            return "changed"
        field = self.FIELDS[self.field_index]
        if event.kind == EVENT_CHARACTER and event.character is not None:
            self.form[field] += event.character
            self.message = ""
            return "changed"
        if event.kind == EVENT_TEXT and event.character is not None:
            self.form[field] = event.character
            self.message = ""
            return "changed"
        if event.kind == EVENT_TAB:
            self.form[field] += " "
            return "changed"
        if event.kind == EVENT_BACKSPACE:
            self.form[field] = self.form[field][:-1]
            self.message = ""
            return "changed"
        if event.kind != EVENT_ENTER:
            return "unchanged"
        if self.field_index + 1 < len(self.FIELDS):
            self.field_index += 1
            return "changed"
        try:
            shortcut = SSHShortcut(
                self.form["name"].strip(), self.form["host"].strip(),
                self.form["user"].strip(), int(self.form["port"]),
                self.form["command"].strip(),
            )
            if self.edit_index is None:
                self.store.add(shortcut)
            else:
                self.store.replace(self.edit_index, shortcut)
            self.shortcuts = self.store.list()
            self.mode = self.LIST_MODE
            self.selected_index = 0
            self.message = "Saved"
        except (ValueError, SSHShortcutError) as exc:
            self.message = str(exc)
        return "changed"

    def _page_count(self) -> int:
        return max(1, (len(self._wrapped or [""]) + self._row_count - 1) // self._row_count)

    def _keep_visible(self, count: int) -> None:
        self.selected_index = min(self.selected_index, max(0, count - 1))
        if self.selected_index < self.list_offset:
            self.list_offset = self.selected_index
        elif self.selected_index >= self.list_offset + self._row_count:
            self.list_offset = self.selected_index - self._row_count + 1
        self.list_offset = min(self.list_offset, max(0, count - self._row_count))
