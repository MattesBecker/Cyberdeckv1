from dataclasses import dataclass
from typing import Optional, Tuple


EVENT_CHARACTER = "character"
EVENT_TEXT = "text"
EVENT_ENTER = "enter"
EVENT_ESCAPE = "escape"
EVENT_TAB = "tab"
EVENT_BACKSPACE = "backspace"
EVENT_UP = "up"
EVENT_DOWN = "down"
EVENT_LEFT = "left"
EVENT_RIGHT = "right"
EVENT_SPECIAL = "special"
EVENT_EOF = "eof"
EVENT_INVALID = "invalid"


class InputError(RuntimeError):
    """Raised when an input source cannot be initialized or read."""


@dataclass(frozen=True)
class InputEvent:
    """One source-independent keyboard event."""

    kind: str
    character: Optional[str] = None
    code: Optional[int] = None


def command_for_event(event: InputEvent) -> str:
    """Map an input event to the application's existing command names."""
    direct_commands = {
        EVENT_UP: "up",
        EVENT_DOWN: "down",
        EVENT_LEFT: "back",
        EVENT_RIGHT: "select",
        EVENT_ENTER: "select",
        EVENT_ESCAPE: "back",
        EVENT_BACKSPACE: "back",
        EVENT_TAB: "down",
        EVENT_EOF: "quit",
    }
    command = direct_commands.get(event.kind)
    if command is not None:
        return command

    if (
        event.kind in (EVENT_CHARACTER, EVENT_TEXT)
        and event.character is not None
    ):
        return {
            "w": "up",
            "s": "down",
            "b": "back",
            "d": "delete",
            "q": "quit",
            "y": "yes",
            "n": "no",
        }.get(event.character.lower(), "invalid")
    return "invalid"


class InputSource:
    """Common interface for CLI and physical keyboard input."""

    name = "input"

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def read_event(self) -> InputEvent:
        raise NotImplementedError

    def read_line(self, prompt: str = "") -> Optional[str]:
        """Read one editable line from key events; Escape cancels it."""
        characters = []
        print(prompt, end="", flush=True)

        while True:
            event = self.read_event()
            if event.kind == EVENT_CHARACTER and event.character is not None:
                characters.append(event.character)
                print(event.character, end="", flush=True)
            elif event.kind == EVENT_TAB:
                characters.append("\t")
                print("\t", end="", flush=True)
            elif event.kind == EVENT_BACKSPACE:
                if characters:
                    characters.pop()
                    print("\b \b", end="", flush=True)
            elif event.kind == EVENT_ENTER:
                print()
                return "".join(characters)
            elif event.kind in (EVENT_ESCAPE, EVENT_EOF):
                print()
                return None
            elif event.kind == EVENT_SPECIAL:
                code = "unknown" if event.code is None else str(event.code)
                print("\nIgnoring unsupported special key {0}.".format(code))
                print(prompt + "".join(characters), end="", flush=True)

    def read_note_input(self) -> Optional[Tuple[str, str]]:
        """Read a title and simple multiline body from this source."""
        title = self.read_line("Note title: ")
        if title is None:
            print("Note creation cancelled.")
            return None

        print('Note text (finish with a single "." on its own line):')
        lines = []
        while True:
            line = self.read_line()
            if line is None:
                print("Note creation cancelled.")
                return None
            if line == ".":
                break
            lines.append(line)
        return title.strip(), "\n".join(lines)

    def read_task_title(self) -> Optional[str]:
        """Read one task title from this source."""
        title = self.read_line("Task title: ")
        if title is None:
            print("Task creation cancelled.")
            return None
        return title.strip()

    def confirm_note_delete(self, title: str) -> bool:
        answer = self.read_line(
            "Delete note '{0}'? y/n: ".format(title)
        )
        return answer is not None and answer.strip().lower() in ("y", "yes")

    def confirm_task_delete(self, title: str) -> bool:
        answer = self.read_line(
            "Delete task '{0}'? y/n: ".format(title)
        )
        return answer is not None and answer.strip().lower() in ("y", "yes")
