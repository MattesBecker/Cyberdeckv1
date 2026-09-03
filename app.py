import argparse
import sys
import traceback
from typing import Dict, Optional, Sequence

from config import INPUT_MODE, MENU_ITEMS, NOTES_DIR, TASKS_FILE
from display import DisplayError, EpaperDisplay
from input_common import InputError, InputEvent, InputSource, command_for_event
from input_factory import INPUT_MODES, create_input_source
from menu import MenuController
from notes_store import NotesStore, NotesStoreError
from pages import BasePage, create_pages
from pages.notes import NotesPage
from pages.tasks import TasksPage
from tasks_store import TasksStore, TasksStoreError


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cyberdeck menu")
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="render views as terminal text without Waveshare hardware",
    )
    parser.add_argument(
        "--input",
        choices=INPUT_MODES,
        default=INPUT_MODE,
        help="input source: auto-detect CardKB, CardKB only, or CLI",
    )
    return parser.parse_args(argv)


def setup_data() -> None:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)


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
    command: str,
    notes_page: NotesPage,
    menu: MenuController,
    input_source: InputSource,
) -> bool:
    if command == "up":
        return notes_page.move_up()
    if command == "down":
        return notes_page.move_down()
    if command == "select":
        result = notes_page.select()
        if result == "new":
            note_input = input_source.read_note_input()
            if note_input is None:
                return False
            title, text = note_input
            notes_page.add_note(title, text)
            return True
        return result in ("opened", "changed")
    if command == "delete":
        note = notes_page.current_note
        if note is None or notes_page.mode != notes_page.NOTE_MODE:
            return False
        if not input_source.confirm_note_delete(note.title):
            return False
        return notes_page.delete_current_note()
    if command == "back":
        if notes_page.back_to_list():
            return True
        return menu.back()
    return False


def handle_tasks_command(
    command: str,
    tasks_page: TasksPage,
    menu: MenuController,
    input_source: InputSource,
) -> bool:
    if command == "up":
        return tasks_page.move_up()
    if command == "down":
        return tasks_page.move_down()
    if command == "select":
        result = tasks_page.select()
        if result == "new":
            title = input_source.read_task_title()
            if title is None:
                return False
            if not title:
                print("Task title must not be empty.")
                return False
            tasks_page.add_task(title)
            return True
        return result == "changed"
    if command == "delete":
        task = tasks_page.selected_task
        if task is None:
            return False
        if not input_source.confirm_task_delete(task.title):
            return False
        return tasks_page.delete_selected_task()
    if command == "back":
        return menu.back()
    return False


def handle_command(
    command: str,
    menu: MenuController,
    pages: Dict[str, BasePage],
    input_source: InputSource,
) -> bool:
    if not menu.is_main_menu():
        page = pages[menu.current_view]
        if isinstance(page, NotesPage):
            try:
                return handle_notes_command(command, page, menu, input_source)
            except NotesStoreError as exc:
                print("Notes error: {0}".format(exc), file=sys.stderr)
                return False
        if isinstance(page, TasksPage):
            try:
                return handle_tasks_command(command, page, menu, input_source)
            except TasksStoreError as exc:
                print("Tasks error: {0}".format(exc), file=sys.stderr)
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
        elif changed and menu.current_view == TasksPage.key:
            tasks_page = pages[TasksPage.key]
            if isinstance(tasks_page, TasksPage):
                try:
                    tasks_page.open_list()
                except TasksStoreError as exc:
                    print("Tasks error: {0}".format(exc), file=sys.stderr)
                    menu.back()
                    return False
        return changed
    if command == "back":
        return menu.back()
    return False


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    display: Optional[EpaperDisplay] = None
    input_source: Optional[InputSource] = None
    exit_code = 0

    try:
        setup_data()
        input_source = create_input_source(args.input)
        print("Input source: {0}".format(input_source.name))
        display = EpaperDisplay(enabled=not args.no_display)
        display.initialize()

        menu = MenuController(MENU_ITEMS)
        tasks_store = TasksStore(TASKS_FILE)
        tasks_store.ensure_file()
        pages = create_pages(NotesStore(NOTES_DIR), tasks_store)
        render_current_view(display, menu, pages)

        while True:
            event = input_source.read_event()
            command = command_for_event(event)
            if command == "quit":
                break
            if command == "invalid":
                _print_unknown_input(event)
                continue
            if handle_command(command, menu, pages, input_source):
                render_current_view(display, menu, pages)
    except KeyboardInterrupt:
        print("\nStopping Cyberdeck.")
    except NotesStoreError as exc:
        print("Notes error: {0}".format(exc), file=sys.stderr)
        exit_code = 1
    except TasksStoreError as exc:
        print("Tasks error: {0}".format(exc), file=sys.stderr)
        exit_code = 1
    except InputError as exc:
        print("Input error: {0}".format(exc), file=sys.stderr)
        exit_code = 1
    except DisplayError as exc:
        print("Display error: {0}".format(exc), file=sys.stderr)
        exit_code = 1
    except Exception as exc:
        print("Unexpected Cyberdeck error: {0}".format(exc), file=sys.stderr)
        traceback.print_exc()
        exit_code = 1
    finally:
        if input_source is not None:
            input_source.close()
        if display is not None:
            try:
                display.sleep()
            except DisplayError as exc:
                print("Shutdown warning: {0}".format(exc), file=sys.stderr)
                exit_code = 1

    return exit_code


def _print_unknown_input(event: InputEvent) -> None:
    if isinstance(event.code, int):
        print(
            "Unsupported input code {0} (0x{0:02X}); ignoring.".format(
                event.code
            )
        )
        return
    if event.code is not None:
        print("Unsupported input code {0}; ignoring.".format(event.code))
        return
    print("Unknown command. Use arrows, Enter, Esc, w, s, b, d, or q.")


if __name__ == "__main__":
    raise SystemExit(main())
