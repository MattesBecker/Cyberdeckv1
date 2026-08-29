import argparse
import sys
import traceback
from typing import Dict, Optional, Sequence

from config import MENU_ITEMS, NOTES_DIR, TASKS_FILE
from display import DisplayError, EpaperDisplay
from input_cli import confirm_note_delete, read_command, read_note_input
from menu import MenuController
from notes_store import NotesStore, NotesStoreError
from pages import BasePage, create_pages
from pages.notes import NotesPage


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


def handle_notes_command(
    command: str, notes_page: NotesPage, menu: MenuController
) -> bool:
    if command == "up":
        return notes_page.move_up()
    if command == "down":
        return notes_page.move_down()
    if command == "select":
        result = notes_page.select()
        if result == "new":
            note_input = read_note_input()
            if note_input is None:
                return False
            title, text = note_input
            notes_page.add_note(title, text)
            return True
        return result == "opened"
    if command == "delete":
        note = notes_page.current_note
        if note is None or notes_page.mode != notes_page.NOTE_MODE:
            return False
        if not confirm_note_delete(note.title):
            return False
        return notes_page.delete_current_note()
    if command == "back":
        if notes_page.back_to_list():
            return True
        return menu.back()
    return False


def handle_command(
    command: str,
    menu: MenuController,
    pages: Dict[str, BasePage],
) -> bool:
    if not menu.is_main_menu():
        page = pages[menu.current_view]
        if isinstance(page, NotesPage):
            try:
                return handle_notes_command(command, page, menu)
            except NotesStoreError as exc:
                print("Notes error: {0}".format(exc), file=sys.stderr)
                return False
        if command == "back":
            return menu.back()
        return False

    if command == "up":
        return menu.move_up()
    if command == "down":
        return menu.move_down()
    if command == "select":
        changed = menu.select()
        if changed and menu.current_view == NotesPage.key:
            notes_page = pages[NotesPage.key]
            if isinstance(notes_page, NotesPage):
                notes_page.open_list()
        return changed
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
        pages = create_pages(NotesStore(NOTES_DIR))
        render_current_view(display, menu, pages)

        while True:
            command = read_command()
            if command == "quit":
                break
            if command == "invalid":
                print("Unknown command. Use w, s, Enter, b, d, or q.")
                continue
            if handle_command(command, menu, pages):
                render_current_view(display, menu, pages)
    except KeyboardInterrupt:
        print("\nStopping Cyberdeck.")
    except NotesStoreError as exc:
        print("Notes error: {0}".format(exc), file=sys.stderr)
        exit_code = 1
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
