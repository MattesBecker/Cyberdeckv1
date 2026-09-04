from typing import TYPE_CHECKING, Optional

from game_logic import Game2048, GameStatsStore, Minesweeper, Sudoku4, TicTacToe
from input_common import (
    EVENT_CHARACTER, EVENT_DOWN, EVENT_ENTER, EVENT_EOF, EVENT_ESCAPE,
    EVENT_LEFT, EVENT_RIGHT, EVENT_TEXT, EVENT_UP, InputEvent,
    command_for_event,
)

from .base import BasePage

if TYPE_CHECKING:
    from display import EpaperDisplay


class _MemoryStats:
    def __init__(self) -> None:
        self.high = 0

    def high_score_2048(self) -> int:
        return self.high

    def update_2048(self, score: int) -> int:
        self.high = max(self.high, score)
        return self.high


class GamesPage(BasePage):
    key = "games"
    title = "GAMES"
    MENU_MODE = "menu"
    GAME_2048_MODE = "2048"
    TTT_MENU_MODE = "tic_tac_toe_menu"
    TTT_MODE = "tic_tac_toe"
    TTT_TWO_PLAYER_MODE = "tic_tac_toe_two_player"
    SUDOKU_MODE = "sudoku"
    MINES_MODE = "minesweeper"
    MENU_ITEMS = ("2048", "Tic-Tac-Toe", "Sudoku", "Minesweeper", "Back")
    TTT_MENU_ITEMS = ("1 Player", "2 Players", "Back")

    def __init__(self, stats_store: Optional[GameStatsStore] = None) -> None:
        self.stats_store = stats_store or _MemoryStats()
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.cursor = 0
        self.message = ""
        self.game_2048 = Game2048()
        self.ttt = TicTacToe()
        self.ttt_player = "X"
        self.sudoku = Sudoku4()
        self.minesweeper = Minesweeper()
        self.high_score = self.stats_store.high_score_2048()

    @property
    def ttt_board(self):
        return self.ttt.board

    @property
    def revealed(self):
        return self.minesweeper.revealed

    def open_menu(self) -> None:
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.message = ""

    def move_up(self) -> bool:
        if self.mode in (self.MENU_MODE, self.TTT_MENU_MODE):
            items = self._current_menu_items()
            self.selected_index = (self.selected_index - 1) % len(items)
            return True
        return self._move_cursor("up")

    def move_down(self) -> bool:
        if self.mode in (self.MENU_MODE, self.TTT_MENU_MODE):
            items = self._current_menu_items()
            self.selected_index = (self.selected_index + 1) % len(items)
            return True
        return self._move_cursor("down")

    def select(self) -> str:
        if self.mode == self.MENU_MODE:
            selected = self.MENU_ITEMS[self.selected_index]
            if selected == "Back":
                return "back"
            self._start(selected)
            return "changed"
        if self.mode == self.TTT_MENU_MODE:
            selected = self.TTT_MENU_ITEMS[self.selected_index]
            if selected == "Back":
                self.open_menu()
            else:
                self._start_ttt(two_players=selected == "2 Players")
            return "changed"
        if self.mode in (self.TTT_MODE, self.TTT_TWO_PLAYER_MODE):
            return "changed" if self._play_ttt() else "unchanged"
        if self.mode == self.SUDOKU_MODE:
            value = (self.sudoku.board[self.cursor] % 4) + 1
            return "changed" if self._set_sudoku(value) else "unchanged"
        if self.mode == self.MINES_MODE:
            return "changed" if self._reveal_mine() else "unchanged"
        if self.mode == self.GAME_2048_MODE and (self.game_2048.game_over or self.game_2048.won):
            self._start("2048")
            return "changed"
        return "unchanged"

    def back_to_menu(self) -> bool:
        if self.mode == self.MENU_MODE:
            return False
        self.open_menu()
        return True

    def handle_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if event.kind == EVENT_ESCAPE:
            return "changed" if self.back_to_menu() else "back"
        if self.mode in (self.MENU_MODE, self.TTT_MENU_MODE):
            command = command_for_event(event)
            if command == "up":
                return "changed" if self.move_up() else "unchanged"
            if command == "down":
                return "changed" if self.move_down() else "unchanged"
            if command == "select":
                return self.select()
            if command == "back":
                if self.mode == self.TTT_MENU_MODE:
                    self.open_menu()
                    return "changed"
                return "back"
            return "invalid"
        direction = self._direction(event)
        if direction is not None:
            if self.mode == self.GAME_2048_MODE:
                changed = self.game_2048.move(direction)
                if changed:
                    self.high_score = self.stats_store.update_2048(self.game_2048.score)
                    self._update_2048_message()
                return "changed" if changed else "unchanged"
            return "changed" if self._move_cursor(direction) else "unchanged"
        text = (event.character or "") if event.kind in (EVENT_CHARACTER, EVENT_TEXT) else ""
        if self.mode == self.SUDOKU_MODE and text in ("0", "1", "2", "3", "4"):
            return "changed" if self._set_sudoku(int(text)) else "unchanged"
        if self.mode == self.MINES_MODE and text.lower() == "f":
            changed = self.minesweeper.toggle_flag(self.cursor)
            self.message = "Flag toggled" if changed else self.message
            return "changed" if changed else "unchanged"
        if text.lower() == "n":
            self._restart_current()
            return "changed"
        if event.kind == EVENT_ENTER:
            return self.select()
        return "invalid"

    def render(self, display: "EpaperDisplay") -> bool:
        if self.mode == self.GAME_2048_MODE:
            rows = [" ".join("{0:4}".format(value or ".") for value in row) for row in self.game_2048.board]
            return display.render_grid_page("2048 S:{0}".format(self.game_2048.score), rows, self.message or "arrows Esc")
        if self.mode == self.TTT_MENU_MODE:
            lines = [
                ("> " if index == self.selected_index else "  ") + label
                for index, label in enumerate(self.TTT_MENU_ITEMS)
            ]
            return display.render_page("TIC-TAC-TOE", lines, "w/s Enter Esc")
        if self.mode in (self.TTT_MODE, self.TTT_TWO_PLAYER_MODE):
            players = "2P" if self.mode == self.TTT_TWO_PLAYER_MODE else "1P"
            return display.render_grid_page(
                "TIC-TAC-TOE {0}".format(players),
                self._ttt_lines(),
                "arrows Enter Esc",
            )
        if self.mode == self.SUDOKU_MODE:
            return display.render_grid_page("SUDOKU 4x4", self._sudoku_lines(), self.message or "1-4 0:clear Esc")
        if self.mode == self.MINES_MODE:
            return display.render_grid_page("MINES 8x5", self._mine_lines(), self.message or "Enter f:flag Esc")
        lines = [("> " if index == self.selected_index else "  ") + label for index, label in enumerate(self.MENU_ITEMS)]
        return display.render_page(self.title, lines, "w/s Enter b")

    def _start(self, selected: str) -> None:
        self.cursor = 0
        if selected == "2048":
            self.game_2048.reset()
            self.mode = self.GAME_2048_MODE
            self._update_2048_message()
        elif selected == "Tic-Tac-Toe":
            self.mode = self.TTT_MENU_MODE
            self.selected_index = 0
            self.message = ""
        elif selected == "Sudoku":
            self.sudoku.new_game()
            self.mode = self.SUDOKU_MODE
            self.message = "Fill 1-4"
        else:
            self.minesweeper.reset()
            self.mode = self.MINES_MODE
            self.message = "First move is safe"

    def _restart_current(self) -> None:
        if self.mode in (self.TTT_MODE, self.TTT_TWO_PLAYER_MODE):
            self._start_ttt(self.mode == self.TTT_TWO_PLAYER_MODE)
            return
        labels = {
            self.GAME_2048_MODE: "2048",
            self.SUDOKU_MODE: "Sudoku",
            self.MINES_MODE: "Minesweeper",
        }
        self._start(labels[self.mode])

    def _play_ttt(self) -> bool:
        if self.mode == self.TTT_TWO_PLAYER_MODE:
            return self._play_ttt_two_player()
        if self.ttt.winner() or self.ttt.draw:
            self._start_ttt(False)
            return True
        if not self.ttt.player_move(self.cursor):
            self.message = "Cell occupied"
            return True
        if self.ttt.winner() == "X":
            self.message = "You win! Enter:new"
        elif self.ttt.draw:
            self.message = "Draw. Enter:new"
        else:
            self.ttt.cpu_move()
            if self.ttt.winner() == "O":
                self.message = "CPU wins. Enter:new"
            elif self.ttt.draw:
                self.message = "Draw. Enter:new"
            else:
                self.message = "Your turn"
        return True

    def _start_ttt(self, two_players: bool) -> None:
        self.cursor = 0
        self.ttt.reset()
        self.ttt_player = "X"
        self.mode = self.TTT_TWO_PLAYER_MODE if two_players else self.TTT_MODE
        self.message = "X turn" if two_players else "You are X"

    def _play_ttt_two_player(self) -> bool:
        if self.ttt.winner() or self.ttt.draw:
            self._start_ttt(True)
            return True
        if not self.ttt.move(self.cursor, self.ttt_player):
            self.message = "Cell occupied"
            return True
        winner = self.ttt.winner()
        if winner:
            self.message = "{0} wins! Enter:new".format(winner)
        elif self.ttt.draw:
            self.message = "Draw. Enter:new"
        else:
            self.ttt_player = "O" if self.ttt_player == "X" else "X"
            self.message = "{0} turn".format(self.ttt_player)
        return True

    def _set_sudoku(self, value: int) -> bool:
        if not self.sudoku.set_value(self.cursor, value):
            self.message = "Fixed cell"
            return True
        if not self.sudoku.is_valid():
            self.message = "Conflict"
        elif self.sudoku.solved:
            self.message = "Solved! n:new"
        else:
            self.message = "OK"
        return True

    def _reveal_mine(self) -> bool:
        if self.minesweeper.lost or self.minesweeper.won:
            self._start("Minesweeper")
            return True
        changed = self.minesweeper.reveal(self.cursor)
        if self.minesweeper.lost:
            self.message = "Boom! Enter:new"
        elif self.minesweeper.won:
            self.message = "Cleared! Enter:new"
        elif changed:
            self.message = "Safe"
        return changed

    def _move_cursor(self, direction: str) -> bool:
        if self.mode in (self.TTT_MODE, self.TTT_TWO_PLAYER_MODE):
            width, count = 3, 9
        elif self.mode == self.SUDOKU_MODE:
            width, count = 4, 16
        elif self.mode == self.MINES_MODE:
            width, count = self.minesweeper.width, self.minesweeper.cell_count
        else:
            return False
        row, col = divmod(self.cursor, width)
        height = count // width
        if direction == "up": row = (row - 1) % height
        elif direction == "down": row = (row + 1) % height
        elif direction == "left": col = (col - 1) % width
        elif direction == "right": col = (col + 1) % width
        else: return False
        self.cursor = row * width + col
        return True

    @staticmethod
    def _direction(event: InputEvent) -> Optional[str]:
        direct = {EVENT_UP: "up", EVENT_DOWN: "down", EVENT_LEFT: "left", EVENT_RIGHT: "right"}
        if event.kind in direct:
            return direct[event.kind]
        if event.kind in (EVENT_CHARACTER, EVENT_TEXT):
            return {"w": "up", "s": "down", "a": "left", "d": "right"}.get((event.character or "").lower())
        return None

    def _current_menu_items(self):
        if self.mode == self.TTT_MENU_MODE:
            return self.TTT_MENU_ITEMS
        return self.MENU_ITEMS

    def _update_2048_message(self) -> None:
        if self.game_2048.won: self.message = "2048! Enter:new"
        elif self.game_2048.game_over: self.message = "Game over Enter:new"
        else: self.message = "Best:{0} arrows Esc".format(self.high_score)

    def _ttt_lines(self):
        lines = []
        for row in range(3):
            cells = []
            for col in range(3):
                index = row * 3 + col
                value = self.ttt.board[index] if self.ttt.board[index] != " " else "."
                cells.append("[{0}]".format(value) if index == self.cursor else " {0} ".format(value))
            lines.append("|".join(cells))
        lines.append(self.message)
        return lines

    def _sudoku_lines(self):
        lines = []
        for row in range(4):
            cells = []
            for col in range(4):
                index = row * 4 + col
                value = str(self.sudoku.board[index] or ".")
                cells.append("[{0}]".format(value) if index == self.cursor else " {0} ".format(value))
            lines.append("|".join(cells))
        return lines

    def _mine_lines(self):
        lines = []
        mines = self.minesweeper.mines or set()
        for row in range(self.minesweeper.height):
            cells = []
            for col in range(self.minesweeper.width):
                index = row * self.minesweeper.width + col
                if index in self.minesweeper.flags: value = "F"
                elif index in self.minesweeper.revealed: value = "*" if index in mines else str(self.minesweeper.adjacent_count(index))
                elif self.minesweeper.lost and index in mines: value = "*"
                else: value = "#"
                cells.append("[{0}]".format(value) if index == self.cursor else " {0} ".format(value))
            lines.append(" ".join(cells))
        return lines
