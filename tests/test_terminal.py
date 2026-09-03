import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from input_cli import CLIInputSource
from input_common import (
    EVENT_BACKSPACE,
    EVENT_CHARACTER,
    EVENT_ENTER,
    EVENT_ESCAPE,
    EVENT_TEXT,
    EVENT_UP,
    InputEvent,
    command_for_event,
)
from pages.terminal import TerminalPage
from services import CommandResult, TerminalService
from terminal_history import TerminalHistoryStore


class FakeDisplay:
    def __init__(self, body_line_count=3, line_width=24):
        self.body_line_count = body_line_count
        self.line_width = line_width
        self.last = None
        self.wrap_count = 0

    def render_page(self, title, lines, footer):
        self.last = (title, list(lines), footer)
        return True

    def wrap_text(self, text):
        self.wrap_count += 1
        wrapped = []
        for line in text.split("\n"):
            if not line:
                wrapped.append("")
                continue
            while len(line) > self.line_width:
                wrapped.append(line[: self.line_width])
                line = line[self.line_width :]
            wrapped.append(line)
        return wrapped or [""]


class FakeTerminalService:
    def __init__(self, stdout="", stderr="", return_code=0):
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return CommandResult(
            command=command,
            arguments=tuple(command.split()),
            stdout=self.stdout,
            stderr=self.stderr,
            return_code=self.return_code,
        )


class TerminalServiceTest(unittest.TestCase):
    def test_echo_hello(self):
        result = TerminalService(timeout=2).execute("echo hello")

        self.assertEqual(result.return_code, 0)
        self.assertEqual(result.stdout.strip(), "hello")
        self.assertEqual(result.stderr, "")

    def test_uname(self):
        result = TerminalService(timeout=2).execute("uname -a")

        self.assertEqual(result.return_code, 0)
        self.assertTrue(result.stdout.strip())

    def test_invalid_command_has_clear_error(self):
        result = TerminalService(timeout=2).execute(
            "cyberdeck-command-that-does-not-exist"
        )

        self.assertIsNone(result.return_code)
        self.assertIn("Command not found", result.error)

    def test_stderr_is_captured(self):
        command = "{0} -c {1}".format(
            shlex.quote(sys.executable),
            shlex.quote("import sys; sys.stderr.write('problem')"),
        )
        result = TerminalService(timeout=2).execute(command)

        self.assertEqual(result.return_code, 0)
        self.assertEqual(result.stderr, "problem")

    def test_timeout_stops_command(self):
        command = "{0} -c {1}".format(
            shlex.quote(sys.executable),
            shlex.quote("import time; time.sleep(1)"),
        )
        result = TerminalService(timeout=0.05).execute(command)

        self.assertTrue(result.timed_out)
        self.assertIn("timed out", result.error)

    def test_shlex_arguments_are_used_without_a_shell(self):
        calls = []

        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            return subprocess.CompletedProcess(arguments, 0, b"ok\n", b"")

        result = TerminalService(timeout=3, runner=runner).execute(
            'echo "hello world"'
        )

        self.assertEqual(result.stdout, "ok\n")
        self.assertEqual(calls[0][0], ["echo", "hello world"])
        self.assertIs(calls[0][1]["shell"], False)
        self.assertEqual(calls[0][1]["timeout"], 3)
        self.assertEqual(calls[0][1]["stdin"], subprocess.DEVNULL)

    def test_invalid_quoting_does_not_start_a_process(self):
        calls = []
        service = TerminalService(
            runner=lambda *args, **kwargs: calls.append((args, kwargs))
        )

        result = service.execute('echo "unfinished')

        self.assertIn("Invalid command line", result.error)
        self.assertEqual(calls, [])

    def test_ansi_sequences_are_removed_from_output(self):
        def runner(arguments, **kwargs):
            return subprocess.CompletedProcess(
                arguments, 0, b"\x1b[31mred\x1b[0m\n", b""
            )

        result = TerminalService(runner=runner).execute("color-test")

        self.assertEqual(result.stdout, "red\n")


class TerminalHistoryStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.history_file = (
            Path(self.temporary_directory.name) / "data" / "history.txt"
        )
        self.store = TerminalHistoryStore(self.history_file, limit=20)

    def test_history_keeps_last_twenty_commands(self):
        for index in range(25):
            self.store.add("command-{0}".format(index))

        history = self.store.load()
        self.assertEqual(len(history), 20)
        self.assertEqual(history[0], "command-5")
        self.assertEqual(history[-1], "command-24")
        self.assertEqual(
            self.history_file.read_text(encoding="utf-8").splitlines(),
            history,
        )

    def test_multiline_input_is_stored_as_one_command(self):
        self.store.add("echo one\necho two")
        self.assertEqual(self.store.load(), ["echo one echo two"])


class TerminalPageTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        history_file = Path(self.temporary_directory.name) / "history.txt"
        self.history = TerminalHistoryStore(history_file, limit=20)
        self.service = FakeTerminalService()
        self.page = TerminalPage(self.service, self.history)
        self.display = FakeDisplay()

    def test_history_navigation_selects_old_and_new_commands(self):
        self.history.add("first")
        self.history.add("second")
        self.page.open_terminal()

        self.assertTrue(self.page.move_up())
        self.assertEqual(self.page.selected_history_command, "second")
        self.assertTrue(self.page.move_up())
        self.assertEqual(self.page.selected_history_command, "first")
        self.assertFalse(self.page.move_up())
        self.assertTrue(self.page.move_down())
        self.assertEqual(self.page.selected_history_command, "second")
        self.assertTrue(self.page.move_down())
        self.assertIsNone(self.page.selected_history_command)

    def test_cardkb_style_events_edit_and_execute_visible_command(self):
        self.page.open_terminal()
        for character in "echo hello":
            action = self.page.handle_event(
                InputEvent(EVENT_CHARACTER, character=character)
            )
            self.assertEqual(action, "changed")

        self.page.render(self.display)
        self.assertIn("$ echo hello", "\n".join(self.display.last[1]))
        self.assertEqual(
            self.page.handle_event(InputEvent(EVENT_BACKSPACE)), "changed"
        )
        self.assertEqual(self.page.command_buffer, "echo hell")
        self.page.handle_event(
            InputEvent(EVENT_CHARACTER, character="o")
        )
        self.assertEqual(
            self.page.handle_event(InputEvent(EVENT_ENTER)), "changed"
        )
        self.assertEqual(self.service.commands, ["echo hello"])
        self.assertEqual(self.page.mode, self.page.OUTPUT_MODE)

    def test_escape_returns_back_from_prompt(self):
        self.page.open_terminal()
        self.assertEqual(
            self.page.handle_event(InputEvent(EVENT_ESCAPE)), "back"
        )

    def test_history_can_be_selected_with_input_event(self):
        self.history.add("uname -a")
        self.page.open_terminal()

        self.assertEqual(
            self.page.handle_event(InputEvent(EVENT_UP)), "changed"
        )
        self.assertEqual(self.page.command_buffer, "uname -a")
        self.page.handle_event(InputEvent(EVENT_ENTER))
        self.assertEqual(self.service.commands, ["uname -a"])

    def test_run_command_shows_stdout_stderr_and_saves_history(self):
        self.service.stdout = "hello\n"
        self.service.stderr = "warning\n"
        self.page.open_terminal()

        self.assertTrue(self.page.run_command("echo hello"))
        self.page.render(self.display)

        output = "\n".join(self.display.last[1])
        self.assertIn("$ echo hello", output)
        self.assertIn("hello", self.page._output_text())
        self.assertIn("stderr:", self.page._output_text())
        self.assertIn("warning", self.page._output_text())
        self.assertEqual(self.history.load(), ["echo hello"])

    def test_long_output_pages_without_rewrapping(self):
        self.service.stdout = "\n".join(
            "line-{0}".format(index) for index in range(8)
        )
        self.page.open_terminal()
        self.page.run_command("long-output")
        self.page.render(self.display)
        self.assertEqual(self.display.wrap_count, 1)

        page_count = self.page._page_count()
        self.assertGreater(page_count, 1)
        for _index in range(page_count - 1):
            self.assertTrue(self.page.move_down())
            self.page.render(self.display)
        self.assertEqual(self.display.wrap_count, 1)
        self.assertFalse(self.page.move_down())


class CLITerminalInputTest(unittest.TestCase):
    def test_complete_cli_line_becomes_text_event(self):
        with patch("builtins.input", return_value="echo hello"):
            event = CLIInputSource().read_event()

        self.assertEqual(event.kind, EVENT_TEXT)
        self.assertEqual(event.character, "echo hello")

    def test_cli_navigation_remains_available(self):
        with patch("builtins.input", return_value="w"):
            event = CLIInputSource().read_event()

        self.assertEqual(event.kind, EVENT_UP)

    def test_single_character_cli_command_is_submitted_text(self):
        with patch("builtins.input", return_value="x"):
            event = CLIInputSource().read_event()

        self.assertEqual(event.kind, EVENT_TEXT)
        self.assertEqual(event.character, "x")

    def test_existing_cli_delete_shortcut_still_maps(self):
        with patch("builtins.input", return_value="d"):
            event = CLIInputSource().read_event()

        self.assertEqual(command_for_event(event), "delete")


if __name__ == "__main__":
    unittest.main()
