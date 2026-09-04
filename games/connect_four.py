import random
from typing import List, Optional


class ConnectFour:
    WIDTH = 7
    HEIGHT = 6

    def __init__(self, rng=None) -> None:
        self.rng = rng or random.Random()
        self.board: List[List[str]] = []
        self.reset()

    def reset(self) -> None:
        self.board = [[" "] * self.WIDTH for _ in range(self.HEIGHT)]

    def available_columns(self) -> List[int]:
        return [column for column in range(self.WIDTH) if self.board[0][column] == " "]

    def drop(self, column: int, mark: str) -> Optional[int]:
        if mark not in ("X", "O") or column not in range(self.WIDTH):
            return None
        for row in range(self.HEIGHT - 1, -1, -1):
            if self.board[row][column] == " ":
                self.board[row][column] = mark
                return row
        return None

    def winner(self) -> Optional[str]:
        directions = ((0, 1), (1, 0), (1, 1), (1, -1))
        for row in range(self.HEIGHT):
            for column in range(self.WIDTH):
                mark = self.board[row][column]
                if mark == " ":
                    continue
                for dr, dc in directions:
                    cells = [
                        (row + step * dr, column + step * dc)
                        for step in range(4)
                    ]
                    if all(
                        0 <= rr < self.HEIGHT
                        and 0 <= cc < self.WIDTH
                        and self.board[rr][cc] == mark
                        for rr, cc in cells
                    ):
                        return mark
        return None

    @property
    def draw(self) -> bool:
        return self.winner() is None and not self.available_columns()

    def choose_cpu_move(self, cpu_mark: str = "O", player_mark: str = "X") -> Optional[int]:
        available = self.available_columns()
        if not available:
            return None
        for mark in (cpu_mark, player_mark):
            for column in available:
                if self._would_win(column, mark):
                    return column

        scores = {column: self._column_score(column, cpu_mark) for column in available}
        best_score = max(scores.values())
        best = [column for column, score in scores.items() if score == best_score]
        return self.rng.choice(best)

    def _would_win(self, column: int, mark: str) -> bool:
        row = self.drop(column, mark)
        if row is None:
            return False
        won = self.winner() == mark
        self.board[row][column] = " "
        return won

    def _column_score(self, column: int, mark: str) -> int:
        row = self.drop(column, mark)
        if row is None:
            return -1000
        score = 8 - abs(3 - column) * 2
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            run = 1
            for sign in (-1, 1):
                step = 1
                while True:
                    rr = row + dr * step * sign
                    cc = column + dc * step * sign
                    if not (0 <= rr < self.HEIGHT and 0 <= cc < self.WIDTH):
                        break
                    if self.board[rr][cc] != mark:
                        break
                    run += 1
                    step += 1
            score += run * run
        self.board[row][column] = " "
        return score
