from typing import Sequence, Tuple


MenuItem = Tuple[str, str]


class MenuController:
    """Keep track of menu selection and the currently open page."""

    MAIN_MENU = "menu"

    def __init__(self, items: Sequence[MenuItem]) -> None:
        if not items:
            raise ValueError("Menu requires at least one item.")
        self.items = tuple(items)
        self.selected_index = 0
        self.current_view = self.MAIN_MENU

    def move_up(self) -> bool:
        if not self.is_main_menu():
            return False
        self.selected_index = (self.selected_index - 1) % len(self.items)
        return True

    def move_down(self) -> bool:
        if not self.is_main_menu():
            return False
        self.selected_index = (self.selected_index + 1) % len(self.items)
        return True

    def select(self) -> bool:
        if not self.is_main_menu():
            return False
        _label, page_key = self.get_current_item()
        self.current_view = page_key
        return True

    def back(self) -> bool:
        if self.is_main_menu():
            return False
        self.current_view = self.MAIN_MENU
        return True

    def get_current_item(self) -> MenuItem:
        return self.items[self.selected_index]

    def is_main_menu(self) -> bool:
        return self.current_view == self.MAIN_MENU
