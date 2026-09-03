import argparse
import sys
import traceback
from typing import Dict, Optional, Sequence

from config import (
    INPUT_MODE,
    LIBRARY_DIR,
    MENU_ITEMS,
    NOTES_DIR,
    TASKS_FILE,
    TERMINAL_COMMAND_TIMEOUT,
    TERMINAL_HISTORY_FILE,
    TERMINAL_HISTORY_LIMIT,
)
from display import DisplayError, EpaperDisplay
from input_common import InputError, InputEvent, InputSource, command_for_event
from input_factory import INPUT_MODES, create_input_source
from menu import MenuController
from notes_store import NotesStore, NotesStoreError
from pages import BasePage, create_pages
from pages.library import LibraryPage
from pages.notes import NotesPage
from pages.tasks import TasksPage
from pages.terminal import TerminalPage
from pages.tools import ToolsPage
from services import (
    LibraryService,
    PowerController,
    SystemActionError,
    TerminalService,
)
from tasks_store import TasksStore, TasksStoreError
from terminal_history import TerminalHistoryStore


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


def handle_tools_command(
    command: str,
    tools_page: ToolsPage,
    menu: MenuController,
    input_source: InputSource,
    no_display: bool,
) -> bool:
    if tools_page.is_confirming:
        if command == "yes":
            action = tools_page.resolve_power_confirmation(
                confirmed=True, simulated=no_display
            )
            if no_display and action is not None:
                print(
                    "No-display mode: {0} simulated; no command executed.".format(
                        action
                    )
                )
            return action is not None
        if command in ("no", "back"):
            return (
                tools_page.resolve_power_confirmation(
                    confirmed=False, simulated=no_display
                )
                is not None
            )
        return False

    if command == "up":
        return tools_page.move_up()
    if command == "down":
        return tools_page.move_down()
    if command == "select":
        result = tools_page.select()
        if result == "ping":
            target = input_source.read_line("Ping host: ")
            if target is None:
                return False
            tools_page.run_ping(target)
            return True
        return result == "changed"
    if command == "back":
        if tools_page.back_to_menu():
            return True
        return menu.back()
    return False


def handle_library_command(
    command: str,
    library_page: LibraryPage,
    menu: MenuController,
) -> bool:
    if command == "up":
        return library_page.move_up()
    if command == "down":
        return library_page.move_down()
    if command == "select":
        return library_page.select() in ("opened", "changed")
    if command == "back":
        if library_page.back():
            return True
        return menu.back()
    return False


def handle_command(
    command: str,
    menu: MenuController,
    pages: Dict[str, BasePage],
    input_source: InputSource,
    no_display: bool = False,
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
        if isinstance(page, ToolsPage):
            return handle_tools_command(
                command, page, menu, input_source, no_display
            )
        if isinstance(page, LibraryPage):
            return handle_library_command(command, page, menu)
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
        elif changed and menu.current_view == ToolsPage.key:
            tools_page = pages[ToolsPage.key]
            if isinstance(tools_page, ToolsPage):
                tools_page.open_menu()
        elif changed and menu.current_view == LibraryPage.key:
            library_page = pages[LibraryPage.key]
            if isinstance(library_page, LibraryPage):
                library_page.open_root()
        elif changed and menu.current_view == TerminalPage.key:
            terminal_page = pages[TerminalPage.key]
            if isinstance(terminal_page, TerminalPage):
                terminal_page.open_terminal()
        return changed
    if command == "back":
        return menu.back()
    return False


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    display: Optional[EpaperDisplay] = None
    input_source: Optional[InputSource] = None
    requested_power_action: Optional[str] = None
    power_controller = PowerController()
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
        pages = create_pages(
            NotesStore(NOTES_DIR),
            tasks_store,
            LibraryService(LIBRARY_DIR),
            TerminalService(TERMINAL_COMMAND_TIMEOUT),
            TerminalHistoryStore(
                TERMINAL_HISTORY_FILE, TERMINAL_HISTORY_LIMIT
            ),
        )
        render_current_view(display, menu, pages)

        while True:
            event = input_source.read_event()
            if not menu.is_main_menu() and menu.current_view == TerminalPage.key:
                terminal_page = pages[TerminalPage.key]
                if not isinstance(terminal_page, TerminalPage):
                    raise RuntimeError("Terminal page is not configured.")
                terminal_action = terminal_page.handle_event(event)
                if terminal_action == "quit":
                    break
                if terminal_action == "invalid":
                    _print_unknown_input(event)
                    continue
                if terminal_action == "back":
                    changed = menu.back()
                else:
                    changed = terminal_action == "changed"
            else:
                command = command_for_event(event)
                if command == "quit":
                    break
                if command == "invalid":
                    _print_unknown_input(event)
                    continue
                changed = handle_command(
                    command,
                    menu,
                    pages,
                    input_source,
                    no_display=args.no_display,
                )
            if changed:
                render_current_view(display, menu, pages)
            tools_page = pages[ToolsPage.key]
            if isinstance(tools_page, ToolsPage):
                requested_power_action = tools_page.take_power_action()
            if requested_power_action is not None:
                break
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
            except KeyboardInterrupt:
                print("\nDisplay sleep interrupted.", file=sys.stderr)
            except DisplayError as exc:
                print("Shutdown warning: {0}".format(exc), file=sys.stderr)
                exit_code = 1

    if requested_power_action is not None:
        try:
            power_controller.execute(requested_power_action)
        except SystemActionError as exc:
            print("System action error: {0}".format(exc), file=sys.stderr)
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
