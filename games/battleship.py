import random
from typing import List, Optional, Sequence, Set, Tuple


class BattleshipBoard:
    SIZE = 6
    FLEET = (3, 2, 2, 1)

    def __init__(self, rng=None) -> None:
        self.rng = rng or random.Random()
        self.ships: List[Set[int]] = []
        self.hits: Set[int] = set()
        self.misses: Set[int] = set()

    def reset(self) -> None:
        self.ships = []
        self.hits = set()
        self.misses = set()

    @property
    def occupied(self) -> Set[int]:
        return set().union(*self.ships) if self.ships else set()

    @property
    def shots(self) -> Set[int]:
        return self.hits | self.misses

    @property
    def all_sunk(self) -> bool:
        return bool(self.ships) and all(ship <= self.hits for ship in self.ships)

    def placement_cells(self, start: int, length: int, horizontal: bool) -> Optional[Set[int]]:
        if start not in range(self.SIZE * self.SIZE) or length < 1:
            return None
        row, column = divmod(start, self.SIZE)
        if horizontal:
            if column + length > self.SIZE:
                return None
            cells = {row * self.SIZE + column + offset for offset in range(length)}
        else:
            if row + length > self.SIZE:
                return None
            cells = {(row + offset) * self.SIZE + column for offset in range(length)}
        return cells

    def can_place(self, start: int, length: int, horizontal: bool) -> bool:
        cells = self.placement_cells(start, length, horizontal)
        return cells is not None and not (cells & self.occupied)

    def place_ship(self, start: int, length: int, horizontal: bool) -> bool:
        cells = self.placement_cells(start, length, horizontal)
        if cells is None or cells & self.occupied:
            return False
        self.ships.append(cells)
        return True

    def auto_place(self, fleet: Sequence[int] = FLEET) -> None:
        self.reset()
        starts = list(range(self.SIZE * self.SIZE))
        for length in fleet:
            choices = [
                (start, horizontal)
                for start in starts
                for horizontal in (True, False)
                if self.can_place(start, length, horizontal)
            ]
            if not choices:
                self.auto_place(fleet)
                return
            start, horizontal = self.rng.choice(choices)
            self.place_ship(start, length, horizontal)

    def shoot(self, index: int) -> str:
        if index not in range(self.SIZE * self.SIZE):
            return "invalid"
        if index in self.shots:
            return "repeat"
        if index not in self.occupied:
            self.misses.add(index)
            return "miss"
        self.hits.add(index)
        ship = next(ship for ship in self.ships if index in ship)
        if self.all_sunk:
            return "win"
        if ship <= self.hits:
            return "sunk"
        return "hit"

    def cell(self, index: int, reveal_ships: bool = False) -> str:
        for ship in self.ships:
            if index in ship and ship <= self.hits:
                return "S"
        if index in self.hits:
            return "X"
        if index in self.misses:
            return "o"
        if reveal_ships and index in self.occupied:
            return "@"
        return "#"


class BattleshipCPU:
    def __init__(self, size: int = BattleshipBoard.SIZE, rng=None) -> None:
        self.size = size
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        self.available = set(range(self.size * self.size))
        self.targets: List[int] = []
        self.active_hits: List[int] = []

    def choose_shot(self) -> Optional[int]:
        self.targets = [target for target in self.targets if target in self.available]
        if self.targets:
            index = self.targets.pop(0)
        elif self.available:
            index = self.rng.choice(sorted(self.available))
        else:
            return None
        self.available.remove(index)
        return index

    def record_result(self, index: int, result: str) -> None:
        if result not in ("hit", "sunk", "win"):
            return
        self.active_hits.append(index)
        if result in ("sunk", "win"):
            self.active_hits = []
            self.targets = []
            return

        candidates = self._directed_targets()
        for candidate in candidates:
            if candidate in self.available and candidate not in self.targets:
                self.targets.append(candidate)

    def _directed_targets(self) -> List[int]:
        if len(self.active_hits) >= 2:
            rows = {index // self.size for index in self.active_hits}
            columns = {index % self.size for index in self.active_hits}
            if len(rows) == 1:
                row = next(iter(rows))
                low = min(index % self.size for index in self.active_hits)
                high = max(index % self.size for index in self.active_hits)
                return [
                    row * self.size + column
                    for column in (low - 1, high + 1)
                    if 0 <= column < self.size
                ]
            if len(columns) == 1:
                column = next(iter(columns))
                low = min(index // self.size for index in self.active_hits)
                high = max(index // self.size for index in self.active_hits)
                return [
                    row * self.size + column
                    for row in (low - 1, high + 1)
                    if 0 <= row < self.size
                ]

        row, column = divmod(self.active_hits[-1], self.size)
        return [
            rr * self.size + cc
            for rr, cc in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            )
            if 0 <= rr < self.size and 0 <= cc < self.size
        ]
