import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from game_logic import Game2048, GameStatsStore, Minesweeper, Sudoku4, TicTacToe
from library import (
    ITEM_TYPE_BACK,
    ITEM_TYPE_BOOKMARKS,
    ITEM_TYPE_HISTORY,
    ITEM_TYPE_SEARCH,
    LibraryDocument,
    LibraryItem,
    LibraryProvider,
    LibraryProviderRegistry,
    SearchResult,
)
from pages.dashboard import DashboardPage
from pages.library import LibraryPage
from pages.settings import SettingsPage
from input_common import EVENT_ENTER, EVENT_RIGHT, InputEvent
from services import (
    Calculator,
    CalculatorError,
    FileViewerError,
    FileViewerService,
    NetworkInfo,
    SSHShortcut,
    SSHShortcutError,
    SSHShortcutService,
    SSHShortcutStore,
    SystemInfo,
)
from settings_store import RuntimeSettings, SettingsError, SettingsStore
from tasks_store import Task
from wiki_store import WikiBookmarksStore, WikiHistoryStore


class CalculatorTest(unittest.TestCase):
    def setUp(self):
        self.calculator = Calculator()

    def test_operators_brackets_negative_and_power(self):
        self.assertEqual(self.calculator.calculate("12 + 5"), 17)
        self.assertEqual(self.calculator.calculate("4 * (3 + 2)"), 20)
        self.assertEqual(self.calculator.calculate("10 / 4"), 2.5)
        self.assertEqual(self.calculator.calculate("10 % 4"), 2)
        self.assertEqual(self.calculator.calculate("2 ^ 8"), 256)
        self.assertEqual(self.calculator.calculate("-2 ^ 2"), -4)

    def test_invalid_zero_division_and_code_are_rejected(self):
        for expression in ("2 +", "10 / 0", "__import__('os').system('id')"):
            with self.subTest(expression=expression), self.assertRaises(CalculatorError):
                self.calculator.calculate(expression)


class FileViewerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "root"
        self.root.mkdir()
        self.service = FileViewerService([self.root], max_bytes=1024)

    def tearDown(self):
        self.temporary.cleanup()

    def test_allowed_directory_and_utf8_file(self):
        folder = self.root / "docs"
        folder.mkdir()
        text_file = folder / "readme.md"
        text_file.write_text("Grüße", encoding="utf-8")
        entries = self.service.list_directory(self.root)
        self.assertEqual(entries[0].title, "docs/")
        self.assertEqual(self.service.open_text(text_file).text, "Grüße")

    def test_outside_symlink_large_and_binary_are_safe(self):
        outside = Path(self.temporary.name) / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        with self.assertRaises(FileViewerError):
            self.service.open_text(outside)
        link = self.root / "escape.txt"
        link.symlink_to(outside)
        with self.assertRaises(FileViewerError):
            self.service.open_text(link)
        large = self.root / "large.log"
        large.write_text("a" * 2000, encoding="utf-8")
        document = self.service.open_text(large)
        self.assertTrue(document.truncated)
        self.assertIn("[truncated", document.text)
        binary = self.root / "binary.log"
        binary.write_bytes(b"a\x00b")
        with self.assertRaises(FileViewerError):
            self.service.open_text(binary)


class SSHShortcutsTest(unittest.TestCase):
    def test_store_validation_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SSHShortcutStore(Path(directory) / "shortcuts.json")
            shortcut = SSHShortcut("Server", "192.168.1.2", "pi", 22, "uptime")
            store.add(shortcut)
            self.assertEqual(store.list(), [shortcut])
            updated = SSHShortcut("Server", "host.local", "pi", 2222, "df -h")
            store.replace(0, updated)
            self.assertEqual(store.list(), [updated])
            store.delete(0)
            self.assertEqual(store.list(), [])
            with self.assertRaises(SSHShortcutError):
                store.add(SSHShortcut("Bad", "-oProxyCommand=x", "pi", 22, "id"))

    def test_subprocess_is_bounded_without_shell(self):
        result = Mock(returncode=0, stdout="up\n", stderr="")
        runner = Mock(return_value=result)
        shortcut = SSHShortcut("Server", "host.local", "pi", 22, "uptime")
        output = SSHShortcutService(runner=runner, timeout=9).run(shortcut)
        self.assertTrue(output.success)
        args, kwargs = runner.call_args
        self.assertEqual(args[0][0], "ssh")
        self.assertIn("BatchMode=yes", args[0])
        self.assertEqual(args[0][-1], "uptime")
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 9)

    def test_timeout_and_error_output(self):
        runner = Mock(side_effect=subprocess.TimeoutExpired(["ssh"], 5))
        shortcut = SSHShortcut("Server", "host.local", "pi", 22, "uptime")
        self.assertIn("timed out", SSHShortcutService(runner=runner).run(shortcut).output)
        failed = Mock(returncode=255, stdout="", stderr="unreachable")
        output = SSHShortcutService(runner=Mock(return_value=failed)).run(shortcut)
        self.assertFalse(output.success)
        self.assertEqual(output.output, "unreachable")


class SettingsTest(unittest.TestCase):
    def test_defaults_load_save_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            self.assertEqual(store.load(), RuntimeSettings())
            changed = store.update(store.load(), boot_enabled=False, boot_duration=1.5)
            self.assertEqual(store.load(), changed)
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(store.load(), RuntimeSettings())

    def test_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(SettingsError):
                store.update(store.load(), boot_duration=99)
            with self.assertRaises(SettingsError):
                store.update(store.load(), start_screen="unsafe")

    def test_settings_page_saves_toggles_and_values(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            page = SettingsPage(store, store.load())
            self.assertEqual(page.handle_event(InputEvent(EVENT_ENTER)), "changed")
            self.assertFalse(store.load().boot_enabled)
            page.selected_index = 1
            page.handle_event(InputEvent(EVENT_RIGHT))
            self.assertEqual(store.load().boot_duration, 1.0)


class WikiStoresTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        moments = iter(
            datetime(2026, 1, 1, 12, 0, second) for second in range(10)
        )
        clock = lambda: next(moments)
        self.bookmarks = WikiBookmarksStore(root / "bookmarks.json", 2, clock)
        self.history = WikiHistoryStore(root / "history.json", 2, clock)

    def tearDown(self):
        self.temporary.cleanup()

    def test_bookmark_add_remove_and_duplicate_toggle(self):
        self.assertTrue(self.bookmarks.toggle("wikipedia", "/content/wiki/A", "A"))
        self.assertTrue(self.bookmarks.contains("wikipedia", "/content/wiki/A"))
        self.assertFalse(self.bookmarks.toggle("wikipedia", "/content/wiki/A", "A"))
        self.assertEqual(self.bookmarks.list(), [])
        self.bookmarks.toggle("wikipedia", "/content/wiki/A", "A")
        self.assertTrue(self.bookmarks.remove("wikipedia", "/content/wiki/A"))

    def test_history_reorders_limits_and_clears(self):
        self.history.record("wikipedia", "/content/wiki/A", "A")
        self.history.record("wikipedia", "/content/wiki/B", "B")
        self.history.record("wikipedia", "/content/wiki/A", "A new")
        self.assertEqual([item.title for item in self.history.list()], ["A new", "B"])
        self.history.record("wikipedia", "/content/wiki/C", "C")
        self.assertEqual([item.title for item in self.history.list()], ["C", "A new"])
        self.history.clear()
        self.assertEqual(self.history.list(), [])


class FakeWikipediaProvider(LibraryProvider):
    key = "wikipedia"
    title = "Wikipedia"
    supports_search = True
    search_title = "WIKIPEDIA"

    def __init__(self):
        self.opened = []

    def list_items(self, container_id=""):
        return [
            LibraryItem(self.key, "search", "Search", ITEM_TYPE_SEARCH),
            LibraryItem(self.key, "bookmarks", "Bookmarks", ITEM_TYPE_BOOKMARKS),
            LibraryItem(self.key, "history", "History", ITEM_TYPE_HISTORY),
            LibraryItem(self.key, "back", "Back", ITEM_TYPE_BACK),
        ]

    def search(self, query):
        return [SearchResult(self.key, "/content/wiki/A", "Article A", "")]

    def open_item(self, item_id):
        self.opened.append(item_id)
        return LibraryDocument(self.key, item_id, "Article A", "Body")

    def get_title(self, item_id):
        return "Article A"


class WikiLibraryPageTest(unittest.TestCase):
    def test_bookmark_reopens_article_and_records_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bookmarks = WikiBookmarksStore(root / "b.json")
            history = WikiHistoryStore(root / "h.json")
            bookmarks.toggle("wikipedia", "/content/wiki/A", "Article A")
            provider = FakeWikipediaProvider()
            page = LibraryPage(LibraryProviderRegistry([provider]), bookmarks, history)
            page.open_provider("wikipedia")
            page.move_down()
            page.select()
            self.assertEqual(page.collection_title, "BOOKMARKS")
            self.assertEqual(page.select(), "opened")
            self.assertEqual(provider.opened, ["/content/wiki/A"])
            self.assertEqual(history.list()[0].title, "Article A")
            self.assertEqual(page._toggle_current_bookmark(), "changed")
            self.assertEqual(bookmarks.list(), [])


class DashboardTest(unittest.TestCase):
    def test_data_offline_and_hidden_fields(self):
        tasks = Mock()
        tasks.list_tasks.return_value = [
            Task("20260101_000000", "Open", False, datetime(2026, 1, 1)),
            Task("20260101_000001", "Done", True, datetime(2026, 1, 1)),
        ]
        network = Mock()
        network.read.return_value = NetworkInfo("DeckNet", "192.168.1.5", 80)
        system = Mock()
        system.read.return_value = SystemInfo("deck", 1, 2, 3, 4, 5 * 1024 ** 3)
        page = DashboardPage(tasks, network, system, RuntimeSettings(dashboard_storage=False), wiki_ready=lambda: True, clock=lambda: datetime(2026, 9, 4, 15, 42))
        page.open()
        self.assertIn("15:42   04.09.", page.lines)
        self.assertIn("WiFi: DeckNet", page.lines)
        self.assertIn("Tasks: 1 open", page.lines)
        self.assertIn("Wiki: ready", page.lines)
        system.read.assert_not_called()
        network.read.return_value = NetworkInfo(None, None, None, "offline")
        page.open(RuntimeSettings(dashboard_tasks=False, dashboard_storage=False))
        self.assertIn("WiFi: offline", page.lines)
        self.assertFalse(any(line.startswith("Tasks:") for line in page.lines))


class Game2048Test(unittest.TestCase):
    def test_move_merge_double_merge_spawn_game_over_and_win(self):
        game = Game2048()
        game.board = [[2, 2, 2, 2], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
        self.assertTrue(game.move("left", spawn=False))
        self.assertEqual(game.board[0], [4, 4, 0, 0])
        self.assertEqual(game.score, 8)
        game.board = [[2048, 0, 0, 0]] + [[0] * 4 for _ in range(3)]
        self.assertTrue(game.won)
        game.board = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]
        self.assertTrue(game.game_over)
        game.board[0][0] = 0
        self.assertTrue(game.spawn_tile())

    def test_high_score_is_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            store = GameStatsStore(path)
            self.assertEqual(store.update_2048(128), 128)
            self.assertEqual(GameStatsStore(path).high_score_2048(), 128)
            self.assertEqual(store.update_2048(64), 128)


class TicTacToeTest(unittest.TestCase):
    def test_player_cpu_win_block_and_draw(self):
        game = TicTacToe()
        self.assertTrue(game.player_move(0))
        game.board = ["O", "O", " ", "X", "X", " ", " ", " ", " "]
        self.assertEqual(game.cpu_move(), 2)
        self.assertEqual(game.winner(), "O")
        game.board = ["X", "X", " ", "O", " ", " ", " ", " ", " "]
        self.assertEqual(game.cpu_move(), 2)
        game.board = ["X", "O", "X", "X", "O", "O", "O", "X", "X"]
        self.assertTrue(game.draw)

    def test_two_player_marks_and_invalid_moves(self):
        game = TicTacToe()
        self.assertTrue(game.move(0, "X"))
        self.assertTrue(game.move(1, "O"))
        self.assertFalse(game.move(0, "O"))
        self.assertFalse(game.move(2, "invalid"))
        self.assertEqual(game.board[:3], ["X", "O", " "])


class SudokuTest(unittest.TestCase):
    def test_fixed_input_validation_and_solved(self):
        game = Sudoku4()
        fixed = next(iter(game.fixed))
        self.assertFalse(game.set_value(fixed, 2))
        editable = next(index for index in range(16) if index not in game.fixed)
        self.assertTrue(game.set_value(editable, game.solution[editable]))
        self.assertTrue(game.is_valid())
        for index in range(16):
            if index not in game.fixed:
                game.set_value(index, game.solution[index])
        self.assertTrue(game.solved)
        editable = next(index for index in range(16) if index not in game.fixed)
        game.set_value(editable, game.solution[(editable + 1) % 16])
        self.assertFalse(game.solved)


class FixedRNG:
    def sample(self, values, count):
        return list(values)[-count:]


class MinesweeperTest(unittest.TestCase):
    def test_first_safe_counts_flood_flag_win_and_loss(self):
        game = Minesweeper(width=4, height=3, mine_count=2, rng=FixedRNG())
        self.assertTrue(game.reveal(0))
        self.assertNotIn(0, game.mines)
        game.reset()
        game.mines = {5}
        self.assertEqual(game.adjacent_count(0), 1)
        self.assertTrue(game.toggle_flag(5))
        self.assertIn(5, game.flags)
        game.toggle_flag(5)
        self.assertTrue(game.reveal(0))
        self.assertGreater(len(game.revealed), 0)
        safe = set(range(game.cell_count)) - game.mines
        game.revealed = safe
        self.assertTrue(game.won)
        game.reset()
        game.mines = {1}
        self.assertTrue(game.reveal(1))
        self.assertTrue(game.lost)


if __name__ == "__main__":
    unittest.main()
