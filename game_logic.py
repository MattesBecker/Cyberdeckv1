import random
from pathlib import Path
from typing import List, Optional, Sequence, Set

from json_store import JSONStoreError, load_json, save_json


class GameStatsStore:
    WORDLE_DEFAULTS = {
        "played": 0,
        "wins": 0,
        "current_streak": 0,
        "best_streak": 0,
    }
    CONNECT_FOUR_DEFAULTS = {
        "cpu_wins": 0,
        "player_wins": 0,
        "draws": 0,
    }
    BATTLESHIP_DEFAULTS = {
        "cpu_games": 0,
        "cpu_wins": 0,
        "cpu_losses": 0,
    }
    BLACKJACK_DEFAULTS = {
        "hands": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "balance": 1000,
    }

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def high_score_2048(self) -> int:
        raw = self._load()
        value = raw.get("high_score_2048", 0) if isinstance(raw, dict) else 0
        return value if isinstance(value, int) and value >= 0 else 0

    def update_2048(self, score: int) -> int:
        high = max(self.high_score_2048(), max(0, int(score)))
        data = self._load()
        data["high_score_2048"] = high
        self._save(data)
        return high

    def wordle_stats(self):
        return self._section("wordle", self.WORDLE_DEFAULTS)

    def record_wordle(self, won: bool):
        stats = self.wordle_stats()
        stats["played"] += 1
        if won:
            stats["wins"] += 1
            stats["current_streak"] += 1
            stats["best_streak"] = max(
                stats["best_streak"], stats["current_streak"]
            )
        else:
            stats["current_streak"] = 0
        return self._update_section("wordle", stats)

    def connect_four_stats(self):
        return self._section("connect_four", self.CONNECT_FOUR_DEFAULTS)

    def record_connect_four(self, result: str):
        fields = {"player": "player_wins", "cpu": "cpu_wins", "draw": "draws"}
        if result not in fields:
            raise ValueError("Invalid Connect Four result")
        stats = self.connect_four_stats()
        stats[fields[result]] += 1
        return self._update_section("connect_four", stats)

    def battleship_stats(self):
        return self._section("battleship", self.BATTLESHIP_DEFAULTS)

    def record_battleship(self, won: bool):
        stats = self.battleship_stats()
        stats["cpu_games"] += 1
        stats["cpu_wins" if won else "cpu_losses"] += 1
        return self._update_section("battleship", stats)

    def blackjack_stats(self):
        return self._section("blackjack", self.BLACKJACK_DEFAULTS)

    def record_blackjack(self, result: str, balance: int):
        if result not in ("blackjack", "win", "loss", "push"):
            raise ValueError("Invalid Blackjack result")
        stats = self.blackjack_stats()
        stats["hands"] += 1
        if result in ("blackjack", "win"):
            stats["wins"] += 1
        elif result == "loss":
            stats["losses"] += 1
        else:
            stats["pushes"] += 1
        stats["balance"] = max(0, int(balance))
        return self._update_section("blackjack", stats)

    def reset_blackjack_balance(self):
        stats = self.blackjack_stats()
        stats["balance"] = self.BLACKJACK_DEFAULTS["balance"]
        return self._update_section("blackjack", stats)

    def _load(self):
        raw = load_json(self.path, {})
        return dict(raw) if isinstance(raw, dict) else {}

    def _section(self, name: str, defaults):
        raw = self._load().get(name, {})
        raw = raw if isinstance(raw, dict) else {}
        values = {}
        for key, default in defaults.items():
            value = raw.get(key, default)
            values[key] = value if isinstance(value, int) and value >= 0 else default
        return values

    def _update_section(self, name: str, values):
        data = self._load()
        data[name] = dict(values)
        self._save(data)
        return dict(values)

    def _save(self, data) -> None:
        try:
            save_json(self.path, data)
        except JSONStoreError:
            pass


class Game2048:
    SIZE = 4

    def __init__(self, rng=None) -> None:
        self.rng = rng or random.Random()
        self.board: List[List[int]] = []
        self.score = 0
        self.reset()

    def reset(self) -> None:
        self.board = [[0] * self.SIZE for _ in range(self.SIZE)]
        self.score = 0
        self.spawn_tile()
        self.spawn_tile()

    def move(self, direction: str, spawn: bool = True) -> bool:
        before = [row[:] for row in self.board]
        gained = 0
        if direction in ("left", "right"):
            rows = []
            for row in self.board:
                source = list(reversed(row)) if direction == "right" else row
                merged, points = self._merge_line(source)
                rows.append(list(reversed(merged)) if direction == "right" else merged)
                gained += points
            self.board = rows
        elif direction in ("up", "down"):
            columns = []
            for column in range(self.SIZE):
                source = [self.board[row][column] for row in range(self.SIZE)]
                if direction == "down":
                    source.reverse()
                merged, points = self._merge_line(source)
                if direction == "down":
                    merged.reverse()
                columns.append(merged)
                gained += points
            self.board = [
                [columns[column][row] for column in range(self.SIZE)]
                for row in range(self.SIZE)
            ]
        else:
            return False
        changed = self.board != before
        if changed:
            self.score += gained
            if spawn:
                self.spawn_tile()
        return changed

    def spawn_tile(self) -> bool:
        empty = [
            (row, col)
            for row in range(self.SIZE)
            for col in range(self.SIZE)
            if self.board[row][col] == 0
        ]
        if not empty:
            return False
        row, col = self.rng.choice(empty)
        self.board[row][col] = 4 if self.rng.random() >= 0.9 else 2
        return True

    @property
    def won(self) -> bool:
        return any(value >= 2048 for row in self.board for value in row)

    @property
    def game_over(self) -> bool:
        if any(0 in row for row in self.board):
            return False
        for row in range(self.SIZE):
            for col in range(self.SIZE):
                value = self.board[row][col]
                if row + 1 < self.SIZE and self.board[row + 1][col] == value:
                    return False
                if col + 1 < self.SIZE and self.board[row][col + 1] == value:
                    return False
        return True

    @classmethod
    def _merge_line(cls, line: Sequence[int]):
        values = [value for value in line if value]
        output = []
        score = 0
        index = 0
        while index < len(values):
            if index + 1 < len(values) and values[index] == values[index + 1]:
                merged = values[index] * 2
                output.append(merged)
                score += merged
                index += 2
            else:
                output.append(values[index])
                index += 1
        output.extend([0] * (cls.SIZE - len(output)))
        return output, score


class TicTacToe:
    WINS = (
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    )

    def __init__(self) -> None:
        self.board = [" "] * 9

    def reset(self) -> None:
        self.board = [" "] * 9

    def winner(self) -> Optional[str]:
        for a, b, c in self.WINS:
            if self.board[a] != " " and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    @property
    def draw(self) -> bool:
        return self.winner() is None and " " not in self.board

    def move(self, index: int, mark: str) -> bool:
        if (
            mark not in ("X", "O")
            or self.winner()
            or self.draw
            or index not in range(9)
            or self.board[index] != " "
        ):
            return False
        self.board[index] = mark
        return True

    def player_move(self, index: int) -> bool:
        return self.move(index, "X")

    def cpu_move(self) -> Optional[int]:
        if self.winner() or self.draw:
            return None
        for mark in ("O", "X"):
            for index, value in enumerate(self.board):
                if value != " ":
                    continue
                self.board[index] = mark
                won = self.winner() == mark
                self.board[index] = " "
                if won:
                    self.board[index] = "O"
                    return index
        if self.board[4] == " ":
            self.board[4] = "O"
            return 4
        for index in (0, 2, 6, 8, 1, 3, 5, 7):
            if self.board[index] == " ":
                self.board[index] = "O"
                return index
        return None


class Sudoku4:
    PUZZLES = (
        ("1004041001404001", "1234341221434321"),
        ("0204300220034001", "1234341221434321"),
        ("3002003001004001", "3412123421434321"),
    )

    def __init__(self) -> None:
        self.puzzle_index = -1
        self.board: List[int] = []
        self.solution: List[int] = []
        self.fixed: Set[int] = set()
        self.new_game()

    def new_game(self) -> None:
        self.puzzle_index = (self.puzzle_index + 1) % len(self.PUZZLES)
        puzzle, solution = self.PUZZLES[self.puzzle_index]
        self.board = [int(value) for value in puzzle]
        self.solution = [int(value) for value in solution]
        self.fixed = {index for index, value in enumerate(self.board) if value}

    def set_value(self, index: int, value: int) -> bool:
        if index not in range(16) or index in self.fixed or value not in range(5):
            return False
        self.board[index] = value
        return True

    def is_valid(self) -> bool:
        groups = []
        groups.extend(self.board[row * 4:(row + 1) * 4] for row in range(4))
        groups.extend([self.board[row * 4 + col] for row in range(4)] for col in range(4))
        groups.extend(
            [self.board[(box_row + row) * 4 + box_col + col] for row in range(2) for col in range(2)]
            for box_row in (0, 2) for box_col in (0, 2)
        )
        for group in groups:
            values = [value for value in group if value]
            if len(values) != len(set(values)):
                return False
        return True

    @property
    def solved(self) -> bool:
        return self.board == self.solution


class Minesweeper:
    def __init__(self, width: int = 8, height: int = 5, mine_count: int = 7, rng=None) -> None:
        self.width = width
        self.height = height
        self.mine_count = mine_count
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        self.mines: Optional[Set[int]] = None
        self.revealed: Set[int] = set()
        self.flags: Set[int] = set()
        self.lost = False

    @property
    def cell_count(self) -> int:
        return self.width * self.height

    @property
    def won(self) -> bool:
        return self.mines is not None and len(self.revealed) == self.cell_count - len(self.mines)

    def reveal(self, index: int) -> bool:
        if index not in range(self.cell_count) or self.lost or self.won or index in self.flags:
            return False
        if self.mines is None:
            self._place_mines(index)
        if index in (self.mines or set()):
            self.revealed.add(index)
            self.lost = True
            return True
        pending = [index]
        before = len(self.revealed)
        while pending:
            current = pending.pop()
            if current in self.revealed or current in self.flags:
                continue
            self.revealed.add(current)
            if self.adjacent_count(current) == 0:
                pending.extend(self.neighbors(current))
        return len(self.revealed) != before

    def toggle_flag(self, index: int) -> bool:
        if index not in range(self.cell_count) or index in self.revealed or self.lost or self.won:
            return False
        if index in self.flags:
            self.flags.remove(index)
        else:
            self.flags.add(index)
        return True

    def adjacent_count(self, index: int) -> int:
        mines = self.mines or set()
        return sum(1 for neighbor in self.neighbors(index) if neighbor in mines)

    def neighbors(self, index: int) -> List[int]:
        row, col = divmod(index, self.width)
        result = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == dc == 0:
                    continue
                rr, cc = row + dr, col + dc
                if 0 <= rr < self.height and 0 <= cc < self.width:
                    result.append(rr * self.width + cc)
        return result

    def _place_mines(self, first_index: int) -> None:
        excluded = {first_index}
        candidates = [index for index in range(self.cell_count) if index not in excluded]
        count = min(self.mine_count, len(candidates))
        self.mines = set(self.rng.sample(candidates, count))
