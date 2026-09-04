from games.connect_four import ConnectFour
from input_common import (
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


class ConnectFourPage:
    MENU_MODE = "menu"
    PLAY_MODE = "play"
    ITEMS = ("Vs CPU", "2 Players", "Back")

    def __init__(self, stats_store) -> None:
        self.stats_store = stats_store
        self.game = ConnectFour()
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.column = 3
        self.vs_cpu = True
        self.player = "X"
        self.message = ""

    def open(self) -> None:
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.message = ""

    def handle_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if event.kind == EVENT_ESCAPE:
            if self.mode == self.PLAY_MODE:
                self.open()
                return "changed"
            return "back"
        if self.mode == self.MENU_MODE:
            if event.kind == EVENT_UP:
                self.selected_index = (self.selected_index - 1) % len(self.ITEMS)
                return "changed"
            if event.kind == EVENT_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.ITEMS)
                return "changed"
            if event.kind == EVENT_ENTER:
                selected = self.ITEMS[self.selected_index]
                if selected == "Back":
                    return "back"
                self._start(selected == "Vs CPU")
                return "changed"
            return "invalid"

        direction = self._horizontal_direction(event)
        if direction:
            self.column = (self.column + direction) % self.game.WIDTH
            return "changed"
        if event.kind == EVENT_ENTER:
            if self.game.winner() or self.game.draw:
                self._start(self.vs_cpu)
            else:
                self._play_column()
            return "changed"
        return "invalid"

    def render(self, display) -> bool:
        if self.mode == self.MENU_MODE:
            lines = [
                ("> " if index == self.selected_index else "  ") + label
                for index, label in enumerate(self.ITEMS)
            ]
            return display.render_page("CONNECT FOUR", lines, "w/s Enter Esc")
        marker = " " + "  " * self.column + "v"
        rows = [
            "|" + "|".join(value if value != " " else "." for value in row) + "|"
            for row in self.game.board
        ]
        title = "CONNECT FOUR " + ("1P" if self.vs_cpu else "2P")
        return display.render_compact_grid_page(title, [marker] + rows, self.message)

    def _start(self, vs_cpu: bool) -> None:
        self.game.reset()
        self.mode = self.PLAY_MODE
        self.vs_cpu = vs_cpu
        self.player = "X"
        self.column = 3
        self.message = "Your turn" if vs_cpu else "P1 turn"

    def _play_column(self) -> None:
        if self.game.drop(self.column, self.player) is None:
            self.message = "Column full"
            return
        if self.game.winner():
            if self.vs_cpu:
                self.message = "You win! Enter:new"
                self.stats_store.record_connect_four("player")
            else:
                winner = "P1" if self.player == "X" else "P2"
                self.message = winner + " wins! Enter:new"
            return
        if self.game.draw:
            self.message = "Draw. Enter:new"
            if self.vs_cpu:
                self.stats_store.record_connect_four("draw")
            return
        if not self.vs_cpu:
            self.player = "O" if self.player == "X" else "X"
            self.message = ("P1" if self.player == "X" else "P2") + " turn"
            return

        cpu_column = self.game.choose_cpu_move()
        if cpu_column is not None:
            self.game.drop(cpu_column, "O")
        if self.game.winner() == "O":
            self.message = "CPU wins. Enter:new"
            self.stats_store.record_connect_four("cpu")
        elif self.game.draw:
            self.message = "Draw. Enter:new"
            self.stats_store.record_connect_four("draw")
        else:
            self.message = "CPU c{0}; your turn".format((cpu_column or 0) + 1)

    @staticmethod
    def _horizontal_direction(event: InputEvent):
        if event.kind == EVENT_LEFT:
            return -1
        if event.kind == EVENT_RIGHT:
            return 1
        if event.kind == EVENT_TEXT and event.character:
            return {"a": -1, "d": 1}.get(event.character.lower())
        return None
