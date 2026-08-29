from typing import Optional, Tuple


COMMANDS = {
    "w": "up",
    "s": "down",
    "": "select",
    "b": "back",
    "d": "delete",
    "q": "quit",
}


def read_command() -> str:
    """Read one blocking command from SSH or the local terminal."""
    try:
        value = input("Command [w/s/Enter/b/d/q]: ").strip().lower()
    except EOFError:
        return "quit"
    return COMMANDS.get(value, "invalid")


def read_note_input() -> Optional[Tuple[str, str]]:
    """Read a title and simple multiline body from the terminal."""
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


def confirm_note_delete(title: str) -> bool:
    """Ask for an explicit terminal confirmation before deletion."""
    try:
        answer = input("Delete note '{0}'? y/n: ".format(title)).strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")
