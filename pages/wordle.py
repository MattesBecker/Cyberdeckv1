from pathlib import Path

from games.wordle import ABSENT, CORRECT, PRESENT, WordleGame, load_word_list
from input_common import (
    EVENT_BACKSPACE,
    EVENT_CHARACTER,
    EVENT_ENTER,
    EVENT_EOF,
    EVENT_ESCAPE,
    EVENT_TEXT,
    InputEvent,
)


class WordlePage:
    def __init__(self, solutions_path: Path, allowed_path: Path, stats_store) -> None:
        solutions = load_word_list(solutions_path)
        allowed = load_word_list(allowed_path)
        self.game = WordleGame(solutions, allowed)
        self.stats_store = stats_store
        self.buffer = ""
        self.message = ""
        self._recorded = False

    def open(self) -> None:
        self.game.reset()
        self.buffer = ""
        self.message = "Type 5 letters"
        self._recorded = False

    def handle_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if event.kind == EVENT_ESCAPE:
            return "back"
        if self.game.game_over:
            if event.kind == EVENT_ENTER:
                self.open()
                return "changed"
            return "unchanged"
        if event.kind == EVENT_BACKSPACE:
            if not self.buffer:
                return "unchanged"
            self.buffer = self.buffer[:-1]
            self.message = ""
            return "changed"
        if event.kind == EVENT_CHARACTER and event.character is not None:
            return self._append(event.character)
        if event.kind == EVENT_TEXT and event.character is not None:
            word = event.character.strip().upper()
            if not word.isascii() or not word.isalpha():
                self.message = "Letters A-Z only"
                return "changed"
            self.buffer = word[: self.game.WORD_LENGTH]
            if len(word) != self.game.WORD_LENGTH:
                self.message = "Enter exactly 5 letters"
                return "changed"
            return self._submit()
        if event.kind == EVENT_ENTER:
            return self._submit()
        return "invalid"

    def render(self, display) -> bool:
        slots = [" " * 15 for _ in range(self.game.MAX_ATTEMPTS)]
        for index, (guess, result) in enumerate(self.game.attempts):
            slots[index] = self._format_guess(guess, result)
        lines = [slots[index] + " " + slots[index + 1] for index in (0, 2, 4)]
        lines.append("> " + self.buffer.ljust(5, "_"))
        lines.append(self.message)
        title = "WORDLE {0} left".format(self.game.attempts_left)
        return display.render_grid_page(title, lines, "[]=right ()=near Esc")

    def _append(self, value: str) -> str:
        changed = False
        for character in value.upper():
            if character.isascii() and character.isalpha() and len(self.buffer) < 5:
                self.buffer += character
                changed = True
        if changed:
            self.message = ""
            return "changed"
        return "unchanged"

    def _submit(self) -> str:
        try:
            self.game.submit(self.buffer)
        except ValueError as exc:
            self.message = str(exc)
            return "changed"
        self.buffer = ""
        if self.game.won:
            stats = self.stats_store.record_wordle(True)
            self.message = "Solved! Streak:{0}".format(stats["current_streak"])
            self._recorded = True
        elif self.game.lost:
            self.stats_store.record_wordle(False)
            self.message = "Answer: " + self.game.solution
            self._recorded = True
        else:
            self.message = "Try again"
        return "changed"

    @staticmethod
    def _format_guess(guess, result) -> str:
        wrappers = {
            CORRECT: ("[", "]"),
            PRESENT: ("(", ")"),
            ABSENT: (" ", " "),
        }
        return "".join(
            wrappers[state][0] + letter + wrappers[state][1]
            for letter, state in zip(guess, result)
        )
