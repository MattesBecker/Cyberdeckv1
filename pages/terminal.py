from typing import TYPE_CHECKING, List, Optional

from services import CommandResult, TerminalService
from terminal_history import TerminalHistoryError, TerminalHistoryStore

from .base import BasePage

if TYPE_CHECKING:
    from display import EpaperDisplay


class TerminalPage(BasePage):
    key = "terminal"
    title = "TERMINAL"

    PROMPT_MODE = "prompt"
    OUTPUT_MODE = "output"

    def __init__(
        self,
        service: TerminalService,
        history_store: TerminalHistoryStore,
    ) -> None:
        self.service = service
        self.history_store = history_store
        self.mode = self.PROMPT_MODE
        self.history: List[str] = []
        self.history_index = 0
        self.result: Optional[CommandResult] = None
        self.page_index = 0
        self._row_count = 5
        self._wrapped_output: Optional[List[str]] = None
        self._history_warning = ""

    def open_terminal(self) -> None:
        self.mode = self.PROMPT_MODE
        self.result = None
        self.page_index = 0
        self._wrapped_output = None
        self._history_warning = ""
        try:
            self.history = self.history_store.load()
        except TerminalHistoryError as exc:
            self.history = []
            self._history_warning = str(exc)
        self.history_index = len(self.history)

    @property
    def selected_history_command(self) -> Optional[str]:
        if self.mode != self.PROMPT_MODE:
            return None
        if 0 <= self.history_index < len(self.history):
            return self.history[self.history_index]
        return None

    def move_up(self) -> bool:
        if self.mode == self.OUTPUT_MODE:
            if self.page_index == 0:
                return False
            self.page_index -= 1
            return True
        if not self.history:
            return False
        new_index = max(0, self.history_index - 1)
        if new_index == self.history_index:
            return False
        self.history_index = new_index
        return True

    def move_down(self) -> bool:
        if self.mode == self.OUTPUT_MODE:
            if self.page_index + 1 >= self._page_count():
                return False
            self.page_index += 1
            return True
        if not self.history:
            return False
        new_index = min(len(self.history), self.history_index + 1)
        if new_index == self.history_index:
            return False
        self.history_index = new_index
        return True

    def run_command(self, command: str) -> bool:
        clean_command = command.strip()
        if not clean_command:
            return False

        self.result = self.service.execute(clean_command)
        self._history_warning = ""
        try:
            self.history = self.history_store.add(clean_command)
        except TerminalHistoryError as exc:
            self.history = (self.history + [clean_command])[
                -self.history_store.limit :
            ]
            self._history_warning = "History: {0}".format(exc)
        self.history_index = len(self.history)
        self.mode = self.OUTPUT_MODE
        self.page_index = 0
        self._wrapped_output = None
        return True

    def render(self, display: "EpaperDisplay") -> bool:
        if self.mode == self.OUTPUT_MODE and self.result is not None:
            return self._render_output(display)
        return self._render_prompt(display)

    def _render_prompt(self, display: "EpaperDisplay") -> bool:
        selected_command = self.selected_history_command
        if selected_command is None:
            lines = ["$", "Enter command"]
        else:
            lines = [
                "$ " + selected_command,
                "History {0}/{1}".format(
                    self.history_index + 1, len(self.history)
                ),
            ]
        if self._history_warning:
            lines.extend(display.wrap_text(self._history_warning))
        return display.render_page(
            self.title, lines[: display.body_line_count], "w/s hist  Enter  b"
        )

    def _render_output(self, display: "EpaperDisplay") -> bool:
        self._row_count = max(1, display.body_line_count)
        if self._wrapped_output is None:
            self._wrapped_output = display.wrap_text(self._output_text())
        page_count = self._page_count()
        self.page_index = min(self.page_index, page_count - 1)
        start = self.page_index * self._row_count
        end = start + self._row_count
        footer = "{0}/{1}  w/s  Enter:new  b".format(
            self.page_index + 1, page_count
        )
        return display.render_page(
            self.title, self._wrapped_output[start:end], footer
        )

    def _output_text(self) -> str:
        result = self.result
        if result is None:
            return "$"

        sections = ["$ " + result.command]
        if result.stdout:
            sections.extend(("", result.stdout.rstrip("\n")))
        if result.stderr:
            sections.extend(("", "stderr:", result.stderr.rstrip("\n")))
        if result.error:
            sections.extend(("", result.error))
        elif result.return_code not in (None, 0):
            sections.extend(("", "[exit {0}]".format(result.return_code)))
        elif not result.stdout and not result.stderr:
            sections.extend(("", "(no output)"))
        if self._history_warning:
            sections.extend(("", self._history_warning))
        return "\n".join(sections)

    def _page_count(self) -> int:
        line_count = len(self._wrapped_output or [""])
        return max(1, (line_count + self._row_count - 1) // self._row_count)
