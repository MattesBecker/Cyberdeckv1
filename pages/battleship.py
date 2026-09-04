from games.battleship import BattleshipBoard, BattleshipCPU
from input_common import (
    EVENT_CHARACTER,
    EVENT_DOWN,
    EVENT_ENTER,
    EVENT_EOF,
    EVENT_ESCAPE,
    EVENT_LEFT,
    EVENT_RIGHT,
    EVENT_TEXT,
    EVENT_UP,
    InputEvent,
)


class BattleshipPage:
    MENU_MODE = "menu"
    PLACEMENT_CHOICE_MODE = "placement_choice"
    MANUAL_MODE = "manual"
    HANDOFF_MODE = "handoff"
    BATTLE_MODE = "battle"
    GAME_OVER_MODE = "game_over"
    MENU_ITEMS = ("Vs CPU", "2 Players", "Back")
    PLACEMENT_ITEMS = ("Auto place", "Manual place", "Back")

    def __init__(self, stats_store) -> None:
        self.stats_store = stats_store
        self.boards = [BattleshipBoard(), BattleshipBoard()]
        self.cpu = BattleshipCPU()
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.cursor = 0
        self.current_player = 0
        self.vs_cpu = True
        self.ship_index = 0
        self.horizontal = True
        self.view_own = False
        self.message = ""
        self.handoff_player = 0
        self.handoff_next = "battle"
        self.handoff_message = ""

    def open(self) -> None:
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.message = ""

    def handle_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if event.kind == EVENT_ESCAPE:
            if self.mode == self.MENU_MODE:
                return "back"
            if self.mode == self.MANUAL_MODE:
                self.mode = self.PLACEMENT_CHOICE_MODE
                self.selected_index = 0
                return "changed"
            self.open()
            return "changed"
        if self.mode in (self.MENU_MODE, self.PLACEMENT_CHOICE_MODE):
            return self._handle_menu(event)
        if self.mode == self.HANDOFF_MODE:
            if event.kind == EVENT_ENTER:
                self._finish_handoff()
                return "changed"
            return "invalid"
        if self.mode == self.MANUAL_MODE:
            return self._handle_manual(event)
        if self.mode == self.GAME_OVER_MODE:
            if event.kind == EVENT_ENTER:
                self._start(self.vs_cpu)
                return "changed"
            return "unchanged"
        return self._handle_battle(event)

    def render(self, display) -> bool:
        if self.mode == self.MENU_MODE:
            return display.render_page(
                "BATTLESHIP", self._menu_lines(self.MENU_ITEMS), "w/s Enter Esc"
            )
        if self.mode == self.PLACEMENT_CHOICE_MODE:
            title = "BATTLESHIP P{0}".format(self.current_player + 1)
            return display.render_page(
                title, self._menu_lines(self.PLACEMENT_ITEMS), "Ships may touch"
            )
        if self.mode == self.HANDOFF_MODE:
            lines = [
                "PASS DEVICE",
                "Player {0}".format(self.handoff_player + 1),
                self.handoff_message,
                "Press Enter",
            ]
            return display.render_page("BATTLESHIP", lines, "Esc: menu")
        if self.mode == self.MANUAL_MODE:
            length = BattleshipBoard.FLEET[self.ship_index]
            direction = "H" if self.horizontal else "V"
            title = "PLACE P{0} L{1} {2}".format(
                self.current_player + 1, length, direction
            )
            footer = self.message or "arrows r:rotate Enter"
            return display.render_compact_grid_page(
                title,
                self._board_lines(self.boards[self.current_player], True, True),
                footer,
            )

        owner = self.current_player if self.view_own else 1 - self.current_player
        board = self.boards[owner]
        label = "OWN" if self.view_own else "TARGET"
        title = "BATTLE P{0} {1}".format(self.current_player + 1, label)
        return display.render_compact_grid_page(
            title,
            self._board_lines(
                board,
                reveal_ships=self.view_own,
                selected=not self.view_own and self.mode == self.BATTLE_MODE,
            ),
            self.message,
        )

    def _handle_menu(self, event: InputEvent) -> str:
        items = self.MENU_ITEMS if self.mode == self.MENU_MODE else self.PLACEMENT_ITEMS
        if event.kind == EVENT_UP:
            self.selected_index = (self.selected_index - 1) % len(items)
            return "changed"
        if event.kind == EVENT_DOWN:
            self.selected_index = (self.selected_index + 1) % len(items)
            return "changed"
        if event.kind != EVENT_ENTER:
            return "invalid"
        selected = items[self.selected_index]
        if selected == "Back":
            if self.mode == self.MENU_MODE:
                return "back"
            self.open()
        elif self.mode == self.MENU_MODE:
            self._start(selected == "Vs CPU")
        else:
            self._choose_placement(selected == "Auto place")
        return "changed"

    def _handle_manual(self, event: InputEvent) -> str:
        direction = self._direction(event)
        if direction:
            self._move_cursor(direction)
            return "changed"
        if self._is_character(event, "r"):
            self.horizontal = not self.horizontal
            self.message = "Horizontal" if self.horizontal else "Vertical"
            return "changed"
        if event.kind != EVENT_ENTER:
            return "invalid"
        length = BattleshipBoard.FLEET[self.ship_index]
        if not self.boards[self.current_player].place_ship(
            self.cursor, length, self.horizontal
        ):
            self.message = "Cannot place there"
            return "changed"
        self.ship_index += 1
        self.message = "Placed"
        if self.ship_index == len(BattleshipBoard.FLEET):
            self._placement_complete()
        return "changed"

    def _handle_battle(self, event: InputEvent) -> str:
        if self._is_character(event, "v"):
            self.view_own = not self.view_own
            self.message = "v: switch view"
            return "changed"
        if self.view_own:
            return "unchanged"
        direction = self._direction(event)
        if direction:
            self._move_cursor(direction)
            return "changed"
        if event.kind == EVENT_ENTER:
            self._shoot()
            return "changed"
        return "invalid"

    def _start(self, vs_cpu: bool) -> None:
        self.vs_cpu = vs_cpu
        self.boards = [BattleshipBoard(), BattleshipBoard()]
        self.cpu.reset()
        if vs_cpu:
            self.boards[1].auto_place()
        self.current_player = 0
        self.selected_index = 0
        self.cursor = 0
        self.view_own = False
        self.mode = self.PLACEMENT_CHOICE_MODE
        self.message = ""

    def _choose_placement(self, automatic: bool) -> None:
        board = self.boards[self.current_player]
        if automatic:
            board.auto_place()
            self._placement_complete()
            return
        board.reset()
        self.ship_index = 0
        self.cursor = 0
        self.horizontal = True
        self.message = ""
        self.mode = self.MANUAL_MODE

    def _placement_complete(self) -> None:
        if self.vs_cpu:
            self.mode = self.BATTLE_MODE
            self.current_player = 0
            self.cursor = 0
            self.view_own = False
            self.message = "Enter:fire v:view Esc"
            return
        if self.current_player == 0:
            self._set_handoff(1, "placement", "Place your fleet")
        else:
            self._set_handoff(0, "battle", "Your turn")

    def _set_handoff(self, player: int, next_mode: str, message: str) -> None:
        self.handoff_player = player
        self.handoff_next = next_mode
        self.handoff_message = message
        self.mode = self.HANDOFF_MODE
        self.view_own = False

    def _finish_handoff(self) -> None:
        self.current_player = self.handoff_player
        self.cursor = 0
        self.view_own = False
        self.message = "Enter:fire v:view Esc"
        if self.handoff_next == "placement":
            self.mode = self.PLACEMENT_CHOICE_MODE
            self.selected_index = 0
        else:
            self.mode = self.BATTLE_MODE

    def _shoot(self) -> None:
        target = self.boards[1 - self.current_player]
        result = target.shoot(self.cursor)
        if result == "repeat":
            self.message = "Already targeted"
            return
        if result == "invalid":
            return
        if result == "win":
            self.message = "You win! Enter:new" if self.vs_cpu else "P{0} wins! Enter:new".format(self.current_player + 1)
            self.mode = self.GAME_OVER_MODE
            if self.vs_cpu:
                self.stats_store.record_battleship(False)
            return
        if not self.vs_cpu:
            shooter = self.current_player
            self._set_handoff(
                1 - shooter,
                "battle",
                "P{0}: {1}".format(shooter + 1, result),
            )
            return

        cpu_index = self.cpu.choose_shot()
        cpu_result = self.boards[0].shoot(cpu_index) if cpu_index is not None else "miss"
        if cpu_index is not None:
            self.cpu.record_result(cpu_index, cpu_result)
        if cpu_result == "win":
            self.message = "CPU wins. Enter:new"
            self.mode = self.GAME_OVER_MODE
            self.stats_store.record_battleship(True)
        else:
            self.message = "You:{0} CPU:{1} v:view".format(result, cpu_result)

    def _move_cursor(self, direction: str) -> None:
        row, column = divmod(self.cursor, BattleshipBoard.SIZE)
        if direction == "up":
            row = (row - 1) % BattleshipBoard.SIZE
        elif direction == "down":
            row = (row + 1) % BattleshipBoard.SIZE
        elif direction == "left":
            column = (column - 1) % BattleshipBoard.SIZE
        elif direction == "right":
            column = (column + 1) % BattleshipBoard.SIZE
        self.cursor = row * BattleshipBoard.SIZE + column

    def _board_lines(self, board, reveal_ships: bool, selected: bool):
        lines = []
        for row in range(BattleshipBoard.SIZE):
            cells = []
            for column in range(BattleshipBoard.SIZE):
                index = row * BattleshipBoard.SIZE + column
                value = board.cell(index, reveal_ships)
                cells.append(
                    "[{0}]".format(value)
                    if selected and index == self.cursor
                    else " {0} ".format(value)
                )
            lines.append(" ".join(cells))
        return lines

    def _menu_lines(self, items):
        return [
            ("> " if index == self.selected_index else "  ") + label
            for index, label in enumerate(items)
        ]

    @staticmethod
    def _direction(event: InputEvent):
        direct = {
            EVENT_UP: "up",
            EVENT_DOWN: "down",
            EVENT_LEFT: "left",
            EVENT_RIGHT: "right",
        }
        if event.kind in direct:
            return direct[event.kind]
        if event.kind == EVENT_TEXT and event.character:
            return {
                "w": "up",
                "s": "down",
                "a": "left",
                "d": "right",
            }.get(event.character.lower())
        return None

    @staticmethod
    def _is_character(event: InputEvent, expected: str) -> bool:
        return (
            event.kind in (EVENT_CHARACTER, EVENT_TEXT)
            and event.character is not None
            and event.character.lower() == expected
        )
