from typing import Optional, Tuple

from input_common import (
    EVENT_CHARACTER,
    EVENT_ENTER,
    EVENT_EOF,
    EVENT_INVALID,
    InputEvent,
    InputSource,
    command_for_event,
)


COMMANDS = {
    "w": "up",
    "s": "down",
    "": "select",
    "b": "back",
    "d": "delete",
    "q": "quit",
}


class CLIInputSource(InputSource):
    """Keep the existing blocking SSH/terminal input as an input source."""

    name = "cli"

    def read_event(self) -> InputEvent:
        try:
            value = input("Command [w/s/Enter/b/d/q]: ").strip()
        except EOFError:
            return InputEvent(EVENT_EOF)
        if not value:
            return InputEvent(EVENT_ENTER, code=13)
        if len(value) == 1:
            return InputEvent(
                EVENT_CHARACTER,
                character=value,
                code=ord(value),
            )
        return InputEvent(EVENT_INVALID)

    def read_line(self, prompt: str = "") -> Optional[str]:
        try:
            return input(prompt)
        except EOFError:
            return None

    def read_note_input(self) -> Optional[Tuple[str, str]]:
        """Preserve the existing CLI multiline and EOF behavior."""
        try:
            title = input("Note title: ").strip()
        except EOFError:
            print("Note creation cancelled.")
            return None

        print('Note text (finish with a single "." on its own line):')
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line == ".":
                break
            lines.append(line)
        return title, "\n".join(lines)

    def read_task_title(self) -> Optional[str]:
        try:
            return input("Task title: ").strip()
        except EOFError:
            print("Task creation cancelled.")
            return None

    def confirm_note_delete(self, title: str) -> bool:
        try:
            answer = input(
                "Delete note '{0}'? y/n: ".format(title)
            ).strip().lower()
        except EOFError:
            return False
        return answer in ("y", "yes")

    def confirm_task_delete(self, title: str) -> bool:
        try:
            answer = input(
                "Delete task '{0}'? y/n: ".format(title)
            ).strip().lower()
        except EOFError:
            return False
        return answer in ("y", "yes")


def read_command() -> str:
    """Read one blocking command from SSH or the local terminal."""
    return command_for_event(CLIInputSource().read_event())


def read_note_input() -> Optional[Tuple[str, str]]:
    """Read a title and simple multiline body from the terminal."""
    return CLIInputSource().read_note_input()


def confirm_note_delete(title: str) -> bool:
    """Ask for an explicit terminal confirmation before deletion."""
    return CLIInputSource().confirm_note_delete(title)


def read_task_title() -> Optional[str]:
    """Read one task title from the terminal."""
    return CLIInputSource().read_task_title()


def confirm_task_delete(title: str) -> bool:
    """Ask for an explicit terminal confirmation before task deletion."""
    return CLIInputSource().confirm_task_delete(title)
