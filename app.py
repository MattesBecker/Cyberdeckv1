import argparse
import sys
import traceback
from typing import Dict, Optional, Sequence

from config import MENU_ITEMS, NOTES_DIR, TASKS_FILE
from display import DisplayError, EpaperDisplay
from input_cli import read_command
from menu import MenuController
from pages import BasePage, create_pages


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cyberdeck menu")
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="render views as terminal text without Waveshare hardware",
    )
    return parser.parse_args(argv)


def setup_data() -> None:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not TASKS_FILE.exists():
        TASKS_FILE.write_text("[]\n", encoding="utf-8")


def render_current_view(
    display: EpaperDisplay,
    menu: MenuController,
    pages: Dict[str, BasePage],
) -> bool:
    if menu.is_main_menu():
        return display.render_menu(menu.items, menu.selected_index)

    try:
        page = pages[menu.current_view]
    except KeyError as exc:
        raise RuntimeError(
            "No page is registered for '{0}'.".format(menu.current_view)
        ) from exc
    return page.render(display)


def handle_command(command: str, menu: MenuController) -> bool:
    if command == "up":
        return menu.move_up()
    if command == "down":
        return menu.move_down()
    if command == "select":
        return menu.select()
    if command == "back":
        return menu.back()
    return False


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    display: Optional[EpaperDisplay] = None
    exit_code = 0

    try:
        setup_data()
        display = EpaperDisplay(enabled=not args.no_display)
        display.initialize()

        menu = MenuController(MENU_ITEMS)
        pages = create_pages()
        render_current_view(display, menu, pages)

        while True:
            command = read_command()
            if command == "quit":
                break
            if command == "invalid":
                print("Unknown command. Use w, s, Enter, b, or q.")
                continue
            if handle_command(command, menu):
                render_current_view(display, menu, pages)
    except KeyboardInterrupt:
        print("\nStopping Cyberdeck.")
    except DisplayError as exc:
        print("Display error: {0}".format(exc), file=sys.stderr)
        exit_code = 1
    except Exception as exc:
        print("Unexpected Cyberdeck error: {0}".format(exc), file=sys.stderr)
        traceback.print_exc()
        exit_code = 1
    finally:
        if display is not None:
            try:
                display.sleep()
            except DisplayError as exc:
                print("Shutdown warning: {0}".format(exc), file=sys.stderr)
                exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
