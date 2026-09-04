import io
import signal
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

import app
from config import BOOT_LOGO_PATH, BOOT_SCREEN_SECONDS, MENU_ITEMS
from display import EpaperDisplay
from input_cli import CLIInputSource
from input_common import EVENT_FULL_REFRESH, InputEvent, command_for_event
from menu import MenuController
from pages.games import GamesPage


class StartupDisplay:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.events = []

    def show_boot_screen(self, path):
        self.events.append(("boot", path))
        return True

    def request_full_refresh(self):
        self.events.append(("full", None))

    def render_menu(self, items, selected_index):
        self.events.append(("menu", selected_index))
        return True


class FakePageDisplay:
    def __init__(self):
        self.last = None

    def render_page(self, title, lines, footer):
        self.last = (title, list(lines), footer)
        return True


class StartupSequenceTest(unittest.TestCase):
    def test_bootscreen_waits_half_second_then_forces_full_main_menu(self):
        display = StartupDisplay(enabled=True)
        menu = MenuController(MENU_ITEMS)

        def sleeper(seconds):
            display.events.append(("sleep", seconds))

        changed = app.show_startup(display, menu, {}, sleeper=sleeper)

        self.assertTrue(changed)
        self.assertEqual(BOOT_SCREEN_SECONDS, 0.5)
        self.assertEqual(
            display.events,
            [
                ("boot", BOOT_LOGO_PATH),
                ("sleep", BOOT_SCREEN_SECONDS),
                ("full", None),
                ("menu", 0),
            ],
        )

    def test_no_display_skips_bootscreen_and_wait(self):
        display = StartupDisplay(enabled=False)
        menu = MenuController(MENU_ITEMS)
        sleeper = Mock()

        app.show_startup(display, menu, {}, sleeper=sleeper)

        self.assertEqual(display.events, [("menu", 0)])
        sleeper.assert_not_called()

    def test_global_full_refresh_event_rerenders_current_view(self):
        display = StartupDisplay(enabled=False)
        menu = MenuController(MENU_ITEMS)

        handled = app.handle_full_refresh_event(
            InputEvent(EVENT_FULL_REFRESH), display, menu, {}
        )

        self.assertTrue(handled)
        self.assertEqual(display.events, [("full", None), ("menu", 0)])
        self.assertEqual(
            command_for_event(InputEvent(EVENT_FULL_REFRESH)), "full_refresh"
        )

    def test_cli_debug_command_emits_full_refresh_event(self):
        with patch("builtins.input", return_value=":refresh"):
            event = CLIInputSource().read_event()
        self.assertEqual(event.kind, EVENT_FULL_REFRESH)


class BootScreenDisplayTest(unittest.TestCase):
    def test_existing_logo_is_fitted_and_centered_on_white(self):
        display = EpaperDisplay(enabled=False)
        with tempfile.TemporaryDirectory() as directory:
            logo_path = Path(directory) / "logo.png"
            Image.new("RGBA", (40, 20), (0, 0, 0, 255)).save(logo_path)
            with patch.object(display, "refresh_full", return_value=True) as refresh_full:
                self.assertTrue(display.show_boot_screen(logo_path))

        frame = refresh_full.call_args.args[0]
        self.assertEqual(frame.mode, "1")
        self.assertEqual(frame.size, (250, 122))
        self.assertEqual(frame.getpixel((0, 0)), 1)
        self.assertEqual(frame.getpixel((125, 61)), 0)

    def test_missing_logo_uses_text_fallback_without_crashing(self):
        display = EpaperDisplay(enabled=False)
        missing = Path("/definitely/missing/cyberdeck-logo.png")
        with patch.object(display, "refresh_full", return_value=True) as refresh_full:
            with self.assertLogs("display", level="WARNING"):
                self.assertTrue(display.show_boot_screen(missing))

        frame = refresh_full.call_args.args[0]
        self.assertEqual(frame.getextrema()[0], 0)

    def test_requested_full_refresh_updates_unchanged_frame_and_resets_counter(self):
        display = EpaperDisplay(enabled=False)
        display.initialize()
        frame = Image.new("1", (display.width, display.height), 1)
        changed_frame = frame.copy()
        ImageDraw.Draw(changed_frame).point((1, 1), fill=0)

        with redirect_stdout(io.StringIO()):
            display.refresh(frame)
            display.refresh(changed_frame)
            self.assertEqual(display.partial_refresh_count, 1)
            display.request_full_refresh()
            refreshed = display.refresh(changed_frame)

        self.assertTrue(refreshed)
        self.assertEqual(display.partial_refresh_count, 0)
        self.assertTrue(display.partial_ready)


class GamesPageTest(unittest.TestCase):
    def setUp(self):
        self.page = GamesPage()
        self.display = FakePageDisplay()

    def test_games_menu_contains_real_games(self):
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "GAMES")
        self.assertEqual(
            self.display.last[1], ["> Tic-Tac-Toe", "  Minesweeper", "  Back"]
        )

    def test_tic_tac_toe_starts_and_accepts_move(self):
        self.assertEqual(self.page.select(), "changed")
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "TIC-TAC-TOE")
        self.assertEqual(self.page.ttt_board, [" "] * 9)
        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.ttt_board[0], "X")
        self.assertIn("O", self.page.ttt_board)
        self.assertTrue(self.page.back_to_menu())

    def test_minesweeper_starts(self):
        self.page.move_down()
        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.mode, self.page.MINES_MODE)
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "MINESWEEPER")
        self.page.select()
        self.assertIn(0, self.page.revealed)

    def test_sync_is_removed_and_games_is_visible(self):
        keys = [key for _label, key in MENU_ITEMS]
        self.assertIn("games", keys)
        self.assertNotIn("sync", keys)
        self.assertFalse((Path("pages") / "sync.py").exists())


class LifecycleCleanupTest(unittest.TestCase):
    def test_sigterm_runs_provider_input_and_display_cleanup(self):
        cleanup_order = []

        class TerminatingInput:
            name = "terminating-test"

            def read_event(self):
                app.handle_sigterm(signal.SIGTERM, None)

            def close(self):
                cleanup_order.append("input")

        class NoDisplay:
            enabled = False

            def initialize(self):
                pass

            def render_menu(self, items, selected_index):
                return True

            def sleep(self):
                cleanup_order.append("display")

        class ProviderRegistry:
            def close(self):
                cleanup_order.append("providers")

        input_source = TerminatingInput()
        display = NoDisplay()
        registry = ProviderRegistry()
        task_store = Mock()

        with patch.object(app, "setup_data"), patch.object(
            app, "create_input_source", return_value=input_source
        ), patch.object(app, "EpaperDisplay", return_value=display), patch.object(
            app, "TasksStore", return_value=task_store
        ), patch.object(app, "LocalLibraryProvider", return_value=Mock()), patch.object(
            app, "KiwixProvider", return_value=Mock()
        ), patch.object(
            app, "LibraryProviderRegistry", return_value=registry
        ), patch.object(app, "create_pages", return_value={}), redirect_stdout(io.StringIO()):
            exit_code = app.main(["--no-display", "--input=cli"])

        self.assertEqual(exit_code, 0)
        task_store.ensure_file.assert_called_once_with()
        self.assertEqual(cleanup_order, ["providers", "input", "display"])


class SystemdServiceTest(unittest.TestCase):
    def test_service_runs_offline_as_pi_with_bounded_restart_delay(self):
        service = (Path("systemd") / "cyberdeck.service").read_text(encoding="utf-8")
        self.assertIn("User=pi", service)
        self.assertIn("WorkingDirectory=/home/pi/cyberdeck", service)
        self.assertIn(
            "ExecStart=/usr/bin/python3 /home/pi/cyberdeck/app.py --input=auto",
            service,
        )
        self.assertIn("Restart=on-failure", service)
        self.assertIn("RestartSec=3", service)
        self.assertNotIn("network-online.target", service)


if __name__ == "__main__":
    unittest.main()
