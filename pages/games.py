from typing import TYPE_CHECKING

from .base import BasePage

if TYPE_CHECKING:
    from display import EpaperDisplay


class GamesPage(BasePage):
    """Small menu placeholder for future offline games."""

    key = "games"
    title = "GAMES"
    MENU_MODE = "menu"
    MESSAGE_MODE = "message"
    MENU_ITEMS = ("Snake", "Pong", "Back")

    def __init__(self) -> None:
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.selected_game = ""

    def open_menu(self) -> None:
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.selected_game = ""

    def move_up(self) -> bool:
        if self.mode != self.MENU_MODE:
            return False
        self.selected_index = (self.selected_index - 1) % len(self.MENU_ITEMS)
        return True

    def move_down(self) -> bool:
        if self.mode != self.MENU_MODE:
            return False
        self.selected_index = (self.selected_index + 1) % len(self.MENU_ITEMS)
        return True

    def select(self) -> str:
        if self.mode != self.MENU_MODE:
            return "unchanged"
        selected = self.MENU_ITEMS[self.selected_index]
        if selected == "Back":
            return "back"
        self.selected_game = selected
        self.mode = self.MESSAGE_MODE
        return "changed"

    def back_to_menu(self) -> bool:
        if self.mode != self.MESSAGE_MODE:
            return False
        self.mode = self.MENU_MODE
        self.selected_game = ""
        return True

    def render(self, display: "EpaperDisplay") -> bool:
        if self.mode == self.MESSAGE_MODE:
            return display.render_page(
                self.selected_game, ("Coming soon",), "b: back"
            )

        lines = []
        for index, label in enumerate(self.MENU_ITEMS):
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + label)
        return display.render_page(self.title, lines, "w/s  Enter  b")
