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
from input_common import EVENT_CHARACTER, EVENT_FULL_REFRESH, InputEvent, command_for_event
from menu import MenuController
from pages.games import GamesPage
from pages.dashboard import DashboardPage
from settings_store import RuntimeSettings


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

    def render_page(self, title, lines, footer):
        self.events.append(("page", title))
        return True


class FakePageDisplay:
    def __init__(self):
        self.last = None
        self.renderer = None

    def render_page(self, title, lines, footer):
        self.renderer = "page"
        self.last = (title, list(lines), footer)
        return True

    def render_grid_page(self, title, lines, footer):
        self.renderer = "grid"
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

    def test_default_start_screen_is_dashboard_after_forced_full_refresh(self):
        display = StartupDisplay(enabled=True)
        menu = MenuController(MENU_ITEMS)
        settings = RuntimeSettings(
            dashboard_wifi=False,
            dashboard_tasks=False,
            dashboard_storage=False,
        )
        dashboard = DashboardPage(
            Mock(), Mock(), Mock(), settings, wiki_ready=lambda: False
        )

        app.show_startup(
            display,
            menu,
            {DashboardPage.key: dashboard},
            sleeper=lambda seconds: display.events.append(("sleep", seconds)),
            settings=settings,
        )

        self.assertEqual(menu.current_view, DashboardPage.key)
        self.assertEqual(
            display.events[:3],
            [("boot", BOOT_LOGO_PATH), ("sleep", 0.5), ("full", None)],
        )
        self.assertEqual(display.events[3], ("page", "CYBERDECK"))

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

    def test_long_main_menu_keeps_selected_item_visible(self):
        display = EpaperDisplay(enabled=False)
        display.initialize()
        with patch.object(display, "refresh", return_value=True) as refresh:
            display.render_menu(MENU_ITEMS, len(MENU_ITEMS) - 1)
        preview = refresh.call_args.kwargs["preview_lines"]
        self.assertIn("> Settings", preview)
        self.assertNotIn("> Notes", preview)

    def test_game_grid_font_uses_fixed_character_width(self):
        display = EpaperDisplay(enabled=False)
        draw = Mock()
        display._draw_grid_text(draw, 5, 28, ".XO")
        positions = [call.args[0] for call in draw.text.call_args_list]
        self.assertEqual(
            positions,
            [
                (5, 28),
                (5 + display._grid_cell_width, 28),
                (5 + 2 * display._grid_cell_width, 28),
            ],
        )
        self.assertGreater(display._grid_cell_width, 0)


class GamesPageTest(unittest.TestCase):
    def setUp(self):
        self.page = GamesPage()
        self.display = FakePageDisplay()

    def test_games_menu_contains_real_games(self):
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "GAMES")
        self.assertEqual(
            self.display.last[1],
            ["> 2048", "  Tic-Tac-Toe", "  Sudoku", "  Minesweeper", "  Back"],
        )

    def test_tic_tac_toe_starts_and_accepts_move(self):
        self.page.move_down()
        self.assertEqual(self.page.select(), "changed")
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "TIC-TAC-TOE")
        self.assertEqual(self.display.last[1], ["> 1 Player", "  2 Players", "  Back"])
        self.assertEqual(self.page.select(), "changed")
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "TIC-TAC-TOE 1P")
        self.assertEqual(self.display.renderer, "grid")
        self.assertEqual(self.page.ttt_board, [" "] * 9)
        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.ttt_board[0], "X")
        self.assertIn("O", self.page.ttt_board)
        self.assertTrue(self.page.back_to_menu())

    def test_tic_tac_toe_two_players_alternate_and_win(self):
        self.page.move_down()
        self.page.select()
        self.page.move_down()
        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.mode, self.page.TTT_TWO_PLAYER_MODE)
        self.assertEqual(self.page.ttt_player, "X")

        for index, expected_player in (
            (0, "O"),
            (3, "X"),
            (1, "O"),
            (4, "X"),
        ):
            self.page.cursor = index
            self.assertEqual(self.page.select(), "changed")
            self.assertEqual(self.page.ttt_player, expected_player)

        self.page.cursor = 2
        self.page.select()
        self.assertEqual(self.page.ttt.winner(), "X")
        self.assertEqual(self.page.message, "X wins! Enter:new")
        self.assertNotIn("O", self.page.ttt.board[5:])

        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.ttt_board, [" "] * 9)
        self.assertEqual(self.page.ttt_player, "X")

    def test_tic_tac_toe_mode_menu_back_returns_to_games(self):
        self.page.move_down()
        self.page.select()
        result = self.page.handle_event(InputEvent(EVENT_CHARACTER, "b"))
        self.assertEqual(result, "changed")
        self.assertEqual(self.page.mode, self.page.MENU_MODE)

    def test_minesweeper_starts(self):
        for _ in range(3):
            self.page.move_down()
        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.page.mode, self.page.MINES_MODE)
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "MINES 8x5")
        self.page.select()
        self.assertIn(0, self.page.revealed)

    def test_all_game_grid_rows_keep_fixed_width(self):
        self.page.mode = self.page.TTT_MODE
        self.assertEqual({len(line) for line in self.page._ttt_lines()[:3]}, {11})

        self.page.mode = self.page.SUDOKU_MODE
        self.assertEqual({len(line) for line in self.page._sudoku_lines()}, {15})

        self.page.mode = self.page.MINES_MODE
        before = self.page._mine_lines()
        self.page.cursor = self.page.minesweeper.cell_count - 1
        after = self.page._mine_lines()
        self.assertEqual({len(line) for line in before + after}, {31})

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
