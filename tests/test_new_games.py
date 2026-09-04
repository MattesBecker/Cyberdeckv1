import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from game_logic import GameStatsStore
from games.battleship import BattleshipBoard, BattleshipCPU
from games.blackjack import BlackjackGame, hand_value, is_blackjack
from games.connect_four import ConnectFour
from games.wordle import ABSENT, CORRECT, PRESENT, WordleGame, load_word_list
from input_common import EVENT_DOWN, EVENT_ENTER, EVENT_ESCAPE, EVENT_TEXT, InputEvent
from pages.battleship import BattleshipPage
from pages.blackjack import BlackjackPage
from pages.connect_four import ConnectFourPage
from pages.games import GamesPage
from pages.wordle import WordlePage


class FirstChoiceRNG:
    def choice(self, values):
        return list(values)[0]

    def shuffle(self, values):
        return None


class PageDisplay:
    body_line_count = 5

    def __init__(self):
        self.last = None

    def render_page(self, title, lines, footer):
        self.last = (title, list(lines), footer)
        return True

    def render_grid_page(self, title, lines, footer):
        self.last = (title, list(lines), footer)
        return True

    def render_compact_grid_page(self, title, lines, footer):
        self.last = (title, list(lines), footer)
        return True


class WordleGameTest(unittest.TestCase):
    def test_correct_wrong_invalid_and_six_attempts(self):
        game = WordleGame(["APFEL"], ["RAUCH", "STERN"])
        game.reset("APFEL")
        with self.assertRaises(ValueError):
            game.submit("KURZ")
        with self.assertRaises(ValueError):
            game.submit("ABCDE")
        result = game.submit("RAUCH")
        self.assertFalse(game.won)
        self.assertEqual(len(result), 5)
        for _ in range(5):
            game.submit("STERN")
        self.assertTrue(game.lost)
        self.assertEqual(game.attempts_left, 0)

        game.reset("APFEL")
        self.assertEqual(game.submit("APFEL"), (CORRECT,) * 5)
        self.assertTrue(game.won)

    def test_duplicate_letters_are_consumed_once(self):
        result = WordleGame.evaluate("ALLEE", "APFEL")
        self.assertEqual(
            result,
            (CORRECT, PRESENT, ABSENT, CORRECT, ABSENT),
        )

    def test_local_word_lists_are_ascii_and_separate(self):
        root = Path(__file__).resolve().parents[1] / "data"
        solutions = load_word_list(root / "wordle_solutions.txt")
        allowed = load_word_list(root / "wordle_words.txt")
        self.assertGreaterEqual(len(solutions), 100)
        self.assertTrue(set(solutions) <= set(allowed))
        self.assertTrue(all(len(word) == 5 and word.isascii() for word in allowed))

    def test_wordle_page_accepts_complete_cli_word(self):
        root = Path(__file__).resolve().parents[1] / "data"
        stats = Mock()
        stats.record_wordle.return_value = {"current_streak": 1}
        page = WordlePage(
            root / "wordle_solutions.txt",
            root / "wordle_words.txt",
            stats,
        )
        page.game.reset("APFEL")
        result = page.handle_event(InputEvent(EVENT_TEXT, "APFEL"))
        self.assertEqual(result, "changed")
        self.assertTrue(page.game.won)
        stats.record_wordle.assert_called_once_with(True)


class ConnectFourGameTest(unittest.TestCase):
    def test_gravity_and_full_column(self):
        game = ConnectFour()
        self.assertEqual(game.drop(2, "X"), 5)
        self.assertEqual(game.drop(2, "O"), 4)
        for _ in range(4):
            game.drop(2, "X")
        self.assertIsNone(game.drop(2, "O"))

    def test_horizontal_vertical_diagonal_and_draw(self):
        game = ConnectFour()
        for column in range(4):
            game.drop(column, "X")
        self.assertEqual(game.winner(), "X")

        game.reset()
        for _ in range(4):
            game.drop(2, "O")
        self.assertEqual(game.winner(), "O")

        game.reset()
        for index in (0, 8, 16, 24):
            row, column = divmod(index, game.WIDTH)
            game.board[row][column] = "X"
        self.assertEqual(game.winner(), "X")

        game.board = [
            list("XOOOXXX"),
            list("XOOXOOO"),
            list("XXXOXXO"),
            list("OOXXXOO"),
            list("XOOOXXX"),
            list("OOOXOOX"),
        ]
        self.assertTrue(game.draw)

    def test_cpu_wins_blocks_and_prefers_center(self):
        game = ConnectFour(rng=FirstChoiceRNG())
        game.board[-1][:4] = ["O", "O", "O", " "]
        self.assertEqual(game.choose_cpu_move(), 3)
        game.reset()
        game.board[-1][:4] = ["X", "X", "X", " "]
        self.assertEqual(game.choose_cpu_move(), 3)
        game.reset()
        self.assertEqual(game.choose_cpu_move(), 3)

    def test_two_player_page_switches_turns(self):
        stats = Mock()
        page = ConnectFourPage(stats)
        page.open()
        page.handle_event(InputEvent(EVENT_DOWN))
        page.handle_event(InputEvent(EVENT_ENTER))
        self.assertFalse(page.vs_cpu)
        page.handle_event(InputEvent(EVENT_ENTER))
        self.assertEqual(page.player, "O")
        page.handle_event(InputEvent(EVENT_ENTER))
        self.assertEqual(page.player, "X")
        stats.record_connect_four.assert_not_called()


class BattleshipGameTest(unittest.TestCase):
    def test_valid_invalid_overlap_hit_miss_sunk_and_win(self):
        board = BattleshipBoard()
        self.assertTrue(board.place_ship(0, 3, True))
        self.assertFalse(board.place_ship(2, 2, False))
        self.assertFalse(board.place_ship(5, 2, True))
        self.assertTrue(board.place_ship(6, 1, True))
        self.assertEqual(board.shoot(35), "miss")
        self.assertEqual(board.shoot(0), "hit")
        self.assertEqual(board.shoot(1), "hit")
        self.assertEqual(board.shoot(2), "sunk")
        self.assertEqual(board.shoot(6), "win")
        self.assertTrue(board.all_sunk)
        self.assertEqual(board.cell(0), "S")

    def test_cpu_never_repeats_and_targets_neighbor_after_hit(self):
        cpu = BattleshipCPU(rng=FirstChoiceRNG())
        first = cpu.choose_shot()
        self.assertEqual(first, 0)
        cpu.record_result(first, "hit")
        second = cpu.choose_shot()
        self.assertIn(second, (1, 6))
        shots = {first, second}
        while True:
            shot = cpu.choose_shot()
            if shot is None:
                break
            self.assertNotIn(shot, shots)
            shots.add(shot)
        self.assertEqual(len(shots), 36)

    def test_two_player_handoff_never_renders_a_board(self):
        page = BattleshipPage(Mock())
        display = PageDisplay()
        page._start(False)
        page._choose_placement(True)
        self.assertEqual(page.mode, page.HANDOFF_MODE)
        page.render(display)
        self.assertEqual(display.last[1][0], "PASS DEVICE")
        self.assertFalse(any("#" in line or "@" in line for line in display.last[1]))

        page.handle_event(InputEvent(EVENT_ENTER))
        page._choose_placement(True)
        self.assertEqual(page.mode, page.HANDOFF_MODE)
        page.handle_event(InputEvent(EVENT_ENTER))
        self.assertEqual(page.mode, page.BATTLE_MODE)
        page.handle_event(InputEvent(EVENT_ENTER))
        self.assertEqual(page.mode, page.HANDOFF_MODE)
        self.assertEqual(page.current_player, 0)

    def test_manual_placement_rotates_and_places_ship(self):
        page = BattleshipPage(Mock())
        page._start(False)
        page._choose_placement(False)
        self.assertTrue(page.horizontal)
        page.handle_event(InputEvent(EVENT_TEXT, "r"))
        self.assertFalse(page.horizontal)
        page.handle_event(InputEvent(EVENT_ENTER))
        self.assertEqual(page.boards[0].ships[0], {0, 6, 12})


class BlackjackGameTest(unittest.TestCase):
    def test_aces_and_blackjack(self):
        self.assertEqual(hand_value([("A", "S"), ("9", "H")]), 20)
        self.assertEqual(hand_value([("A", "S"), ("A", "H"), ("9", "D")]), 21)
        self.assertTrue(is_blackjack([("A", "S"), ("K", "H")]))
        self.assertFalse(is_blackjack([("7", "S"), ("7", "H"), ("7", "D")]))
        game = BlackjackGame(balance=100)
        game.start_round(
            10,
            [("A", "S"), ("9", "C"), ("K", "H"), ("7", "D")],
        )
        self.assertEqual(game.result, "blackjack")
        self.assertEqual(game.balance, 115)

    def test_hit_player_bust_and_balance(self):
        deck = [("10", "S"), ("9", "C"), ("6", "D"), ("7", "H"), ("K", "S")]
        game = BlackjackGame(balance=100)
        game.start_round(25, deck)
        game.hit()
        self.assertEqual(game.result, "loss")
        self.assertEqual(game.balance, 75)
        with self.assertRaises(ValueError):
            game.hit()

    def test_dealer_draws_busts_wins_and_pushes(self):
        game = BlackjackGame(balance=100)
        game.start_round(10, [("10", "S"), ("9", "C"), ("8", "D"), ("7", "H"), ("K", "S")])
        self.assertEqual(game.stand(), "win")
        self.assertEqual(hand_value(game.dealer), 26)
        self.assertEqual(game.balance, 110)

        game.start_round(10, [("10", "S"), ("10", "C"), ("7", "D"), ("7", "H")])
        self.assertEqual(game.stand(), "push")
        self.assertEqual(game.balance, 110)

        game.start_round(10, [("9", "S"), ("10", "C"), ("7", "D"), ("8", "H")])
        self.assertEqual(game.stand(), "loss")
        self.assertEqual(game.balance, 100)

    def test_blackjack_balance_reset_and_no_negative_balance(self):
        game = BlackjackGame(balance=5)
        with self.assertRaises(ValueError):
            game.start_round(10)
        game.start_round(5, [("10", "S"), ("10", "C"), ("6", "D"), ("9", "H"), ("K", "S")])
        game.hit()
        self.assertEqual(game.balance, 0)
        self.assertEqual(game.reset_balance(), 1000)

    def test_blackjack_page_hides_dealer_card_and_deducts_bet(self):
        stats = Mock()
        stats.blackjack_stats.return_value = {"balance": 1000}
        page = BlackjackPage(stats)
        page.open()
        page.game = BlackjackGame(balance=1000, rng=FirstChoiceRNG())
        page.handle_event(InputEvent(EVENT_ENTER))
        self.assertEqual(page.mode, page.PLAY_MODE)
        self.assertEqual(page.game.balance, 990)
        display = PageDisplay()
        page.render(display)
        self.assertIn("??", display.last[1][3])


class ExtendedGameStatsTest(unittest.TestCase):
    def test_all_stats_persist_and_keep_existing_high_score(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game_stats.json"
            store = GameStatsStore(path)
            store.update_2048(512)
            first = store.record_wordle(True)
            self.assertEqual(first["current_streak"], 1)
            second = store.record_wordle(True)
            self.assertEqual(second["best_streak"], 2)
            store.record_wordle(False)
            self.assertEqual(store.wordle_stats()["current_streak"], 0)
            store.record_connect_four("player")
            store.record_battleship(False)
            store.record_blackjack("push", 975)

            loaded = GameStatsStore(path)
            self.assertEqual(loaded.high_score_2048(), 512)
            self.assertEqual(loaded.connect_four_stats()["player_wins"], 1)
            self.assertEqual(loaded.battleship_stats()["cpu_losses"], 1)
            self.assertEqual(loaded.blackjack_stats()["balance"], 975)
            self.assertEqual(loaded.reset_blackjack_balance()["balance"], 1000)

    def test_corrupt_or_negative_stats_fall_back_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game_stats.json"
            path.write_text("{broken", encoding="utf-8")
            store = GameStatsStore(path)
            self.assertEqual(store.blackjack_stats()["balance"], 1000)
            path.write_text('{"blackjack":{"balance":-5}}', encoding="utf-8")
            self.assertEqual(store.blackjack_stats()["balance"], 1000)


class GamesMenuIntegrationTest(unittest.TestCase):
    def test_menu_scrolls_to_all_new_games_and_back(self):
        page = GamesPage()
        display = PageDisplay()
        for _ in range(7):
            page.move_down()
        page.render(display)
        self.assertIn("> Blackjack", display.last[1])
        self.assertEqual(len(display.last[1]), 5)
        page.move_down()
        page.render(display)
        self.assertIn("> Back", display.last[1])

    def test_each_new_game_opens_without_a_placeholder(self):
        display = PageDisplay()
        page = GamesPage()
        for index, mode in (
            (4, page.WORDLE_MODE),
            (5, page.CONNECT_FOUR_MODE),
            (6, page.BATTLESHIP_MODE),
            (7, page.BLACKJACK_MODE),
        ):
            page.open_menu()
            page.selected_index = index
            self.assertEqual(page.select(), "changed")
            self.assertEqual(page.mode, mode)
            self.assertIsNotNone(page._active_extra_page())
            page.render(display)
            self.assertTrue(display.last[0])
            self.assertEqual(
                page.handle_event(InputEvent(EVENT_ESCAPE)), "changed"
            )
            self.assertEqual(page.mode, page.MENU_MODE)


if __name__ == "__main__":
    unittest.main()
