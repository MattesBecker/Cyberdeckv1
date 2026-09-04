import random
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


CORRECT = "correct"
PRESENT = "present"
ABSENT = "absent"


def _normalize(word: str) -> str:
    return word.strip().upper()


def _valid_word(word: str) -> bool:
    return len(word) == 5 and word.isascii() and word.isalpha()


def load_word_list(path: Path) -> List[str]:
    words = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        word = _normalize(line)
        if word and not word.startswith("#") and _valid_word(word):
            words.append(word)
    if not words:
        raise ValueError("Word list is empty")
    return list(dict.fromkeys(words))


class WordleGame:
    WORD_LENGTH = 5
    MAX_ATTEMPTS = 6

    def __init__(
        self,
        solutions: Sequence[str],
        allowed_words: Optional[Iterable[str]] = None,
        rng=None,
    ) -> None:
        clean_solutions = [_normalize(word) for word in solutions]
        if not clean_solutions or any(not _valid_word(word) for word in clean_solutions):
            raise ValueError("Solutions must contain five-letter ASCII words")
        allowed = {_normalize(word) for word in (allowed_words or ())}
        allowed.update(clean_solutions)
        if any(not _valid_word(word) for word in allowed):
            raise ValueError("Allowed words must be five-letter ASCII words")
        self.solutions = tuple(dict.fromkeys(clean_solutions))
        self.allowed_words = frozenset(allowed)
        self.rng = rng or random.Random()
        self.solution = ""
        self.attempts: List[Tuple[str, Tuple[str, ...]]] = []
        self.reset()

    def reset(self, solution: Optional[str] = None) -> None:
        selected = _normalize(solution) if solution is not None else self.rng.choice(self.solutions)
        if selected not in self.solutions:
            raise ValueError("Unknown solution")
        self.solution = selected
        self.attempts = []

    @property
    def won(self) -> bool:
        return bool(self.attempts and self.attempts[-1][0] == self.solution)

    @property
    def lost(self) -> bool:
        return len(self.attempts) >= self.MAX_ATTEMPTS and not self.won

    @property
    def game_over(self) -> bool:
        return self.won or self.lost

    @property
    def attempts_left(self) -> int:
        return max(0, self.MAX_ATTEMPTS - len(self.attempts))

    def submit(self, guess: str) -> Tuple[str, ...]:
        normalized = _normalize(guess)
        if self.game_over:
            raise ValueError("Game is over")
        if not _valid_word(normalized):
            raise ValueError("Enter exactly 5 letters")
        if normalized not in self.allowed_words:
            raise ValueError("Word not in list")
        result = self.evaluate(normalized, self.solution)
        self.attempts.append((normalized, result))
        return result

    @staticmethod
    def evaluate(guess: str, solution: str) -> Tuple[str, ...]:
        guess = _normalize(guess)
        solution = _normalize(solution)
        if not _valid_word(guess) or not _valid_word(solution):
            raise ValueError("Words must have exactly five ASCII letters")

        result = [ABSENT] * len(solution)
        remaining = Counter()
        for index, expected in enumerate(solution):
            if guess[index] == expected:
                result[index] = CORRECT
            else:
                remaining[expected] += 1

        for index, letter in enumerate(guess):
            if result[index] == CORRECT:
                continue
            if remaining[letter] > 0:
                result[index] = PRESENT
                remaining[letter] -= 1
        return tuple(result)
