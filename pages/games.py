from typing import TYPE_CHECKING, List, Optional

from input_common import (
    EVENT_DOWN,
    EVENT_ENTER,
    EVENT_ESCAPE,
    EVENT_LEFT,
    EVENT_RIGHT,
    EVENT_UP,
)
from .base import BasePage

if TYPE_CHECKING:
    from display import EpaperDisplay
    from input_common import InputEvent


class GamesPage(BasePage):
    """Small offline games that work well with e-paper and CardKB navigation."""

    key = "games"
    title = "GAMES"
    MENU_MODE = "menu"
    TTT_MODE = "tic_tac_toe"
    MINES_MODE = "minesweeper"
    MENU_ITEMS = ("Tic-Tac-Toe", "Minesweeper", "Back")

    def __init__(self) -> None:
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.cursor = 0
        self.message = ""
        self.ttt_board: List[str] = [" "] * 9
        self.mines = {1, 6, 8}
        self.revealed = set()

    def open_menu(self) -> None:
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.message = ""

    def handle_event(self, event: "InputEvent") -> str:
        if event.kind == EVENT_ESCAPE:
            if self.back_to_menu():
                return "changed"
            return "back"
        if event.kind == EVENT_UP:
            return "changed" if self.move_up() else "unchanged"
        if event.kind == EVENT_DOWN:
            return "changed" if self.move_down() else "unchanged"
        if event.kind == EVENT_LEFT:
            if self.mode == self.MENU_MODE:
                return "back"
            return "changed" if self.move_left() else "unchanged"
        if event.kind == EVENT_RIGHT:
            if self.mode == self.MENU_MODE:
                result = self.select()
                return result
            return "changed" if self.move_right() else "unchanged"
        if event.kind == EVENT_ENTER:
            return self.select()
        return "invalid"

    def move_up(self) -> bool:
        if self.mode == self.MENU_MODE:
            self.selected_index = (self.selected_index - 1) % len(self.MENU_ITEMS)
            return True
        if self.mode in (self.TTT_MODE, self.MINES_MODE):
            self.cursor = (self.cursor - 3) % 9
            return True
        return False

    def move_down(self) -> bool:
        if self.mode == self.MENU_MODE:
            self.selected_index = (self.selected_index + 1) % len(self.MENU_ITEMS)
            return True
        if self.mode in (self.TTT_MODE, self.MINES_MODE):
            self.cursor = (self.cursor + 3) % 9
            return True
        return False

    def move_left(self) -> bool:
        if self.mode not in (self.TTT_MODE, self.MINES_MODE):
            return False
        row = self.cursor // 3
        col = self.cursor % 3
        self.cursor = row * 3 + ((col - 1) % 3)
        return True

    def move_right(self) -> bool:
        if self.mode not in (self.TTT_MODE, self.MINES_MODE):
            return False
        row = self.cursor // 3
        col = self.cursor % 3
        self.cursor = row * 3 + ((col + 1) % 3)
        return True

    def select(self) -> str:
        if self.mode == self.MENU_MODE:
            selected = self.MENU_ITEMS[self.selected_index]
            if selected == "Back":
                return "back"
            if selected == "Tic-Tac-Toe":
                self._start_ttt()
            else:
                self._start_mines()
            return "changed"

        if self.mode == self.TTT_MODE:
            self._play_ttt()
            return "changed"
        if self.mode == self.MINES_MODE:
            self._play_mines()
            return "changed"
        return "unchanged"

    def back_to_menu(self) -> bool:
        if self.mode == self.MENU_MODE:
            return False
        self.open_menu()
        return True

    def render(self, display: "EpaperDisplay") -> bool:
        if self.mode == self.TTT_MODE:
            return display.render_page(
                "TIC-TAC-TOE", self._ttt_lines(), "arrows  Enter  Esc"
            )
        if self.mode == self.MINES_MODE:
            return display.render_page(
                "MINESWEEPER", self._mine_lines(), "arrows  Enter  Esc"
            )

        lines = []
        for index, label in enumerate(self.MENU_ITEMS):
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + label)
        return display.render_page(self.title, lines, "up/down  Enter  Esc")

    def _start_ttt(self) -> None:
        self.mode = self.TTT_MODE
        self.cursor = 0
        self.message = "You are X"
        self.ttt_board = [" "] * 9

    def _play_ttt(self) -> None:
        if self._ttt_winner() or " " not in self.ttt_board:
            self._start_ttt()
            return
        if self.ttt_board[self.cursor] != " ":
            self.message = "Cell occupied"
            return
        self.ttt_board[self.cursor] = "X"
        if self._ttt_winner() == "X":
            self.message = "You win! Enter=restart"
            return
        if " " not in self.ttt_board:
            self.message = "Draw. Enter=restart"
            return
        cpu = self._cpu_move()
        if cpu is not None:
            self.ttt_board[cpu] = "O"
        if self._ttt_winner() == "O":
            self.message = "CPU wins. Enter=restart"
        elif " " not in self.ttt_board:
            self.message = "Draw. Enter=restart"
        else:
            self.message = "Your turn"

    def _cpu_move(self) -> Optional[int]:
        for mark in ("O", "X"):
            for index, value in enumerate(self.ttt_board):
                if value != " ":
                    continue
                self.ttt_board[index] = mark
                won = self._ttt_winner() == mark
                self.ttt_board[index] = " "
                if won:
                    return index
        if self.ttt_board[4] == " ":
            return 4
        for index in (0, 2, 6, 8, 1, 3, 5, 7):
            if self.ttt_board[index] == " ":
                return index
        return None

    def _ttt_winner(self) -> Optional[str]:
        wins = (
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6),
        )
        for a, b, c in wins:
            if (
                self.ttt_board[a] != " "
                and self.ttt_board[a] == self.ttt_board[b] == self.ttt_board[c]
            ):
                return self.ttt_board[a]
        return None

    def _ttt_lines(self):
        lines = []
        for row in range(3):
            cells = []
            for col in range(3):
                index = row * 3 + col
                value = self.ttt_board[index] if self.ttt_board[index] != " " else "."
                cells.append(
                    "[{0}]".format(value)
                    if index == self.cursor
                    else " {0} ".format(value)
                )
            lines.append("|".join(cells))
        lines.append(self.message)
        return lines

    def _start_mines(self) -> None:
        self.mode = self.MINES_MODE
        self.cursor = 0
        self.revealed = set()
        self.message = "Find 6 safe cells"

    def _play_mines(self) -> None:
        if self.message.startswith("Boom") or self.message.startswith("Cleared"):
            self._start_mines()
            return
        if self.cursor in self.revealed:
            self.message = "Already open"
            return
        self.revealed.add(self.cursor)
        if self.cursor in self.mines:
            self.message = "Boom! Enter=restart"
            return
        safe_total = 9 - len(self.mines)
        if len(self.revealed - self.mines) == safe_total:
            self.message = "Cleared! Enter=restart"
        else:
            self.message = "Safe"

    def _adjacent_mines(self, index: int) -> int:
        row, col = divmod(index, 3)
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = row + dr, col + dc
                if 0 <= rr < 3 and 0 <= cc < 3 and rr * 3 + cc in self.mines:
                    count += 1
        return count

    def _mine_lines(self):
        lines = []
        lost = self.message.startswith("Boom")
        for row in range(3):
            cells = []
            for col in range(3):
                index = row * 3 + col
                if index in self.revealed:
                    value = "*" if index in self.mines else str(self._adjacent_mines(index))
                elif lost and index in self.mines:
                    value = "*"
                else:
                    value = "#"
                cells.append(
                    "[{0}]".format(value)
                    if index == self.cursor
                    else " {0} ".format(value)
                )
            lines.append(" ".join(cells))
        lines.append(self.message)
        return lines
