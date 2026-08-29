COMMANDS = {
    "w": "up",
    "s": "down",
    "": "select",
    "b": "back",
    "q": "quit",
}


def read_command() -> str:
    """Read one blocking command from SSH or the local terminal."""
    try:
        value = input("Command [w/s/Enter/b/q]: ").strip().lower()
    except EOFError:
        return "quit"
    return COMMANDS.get(value, "invalid")
