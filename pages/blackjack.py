from games.blackjack import BlackjackGame, card_label, hand_value
from input_common import (
    EVENT_DOWN,
    EVENT_ENTER,
    EVENT_EOF,
    EVENT_ESCAPE,
    EVENT_UP,
    InputEvent,
)


class BlackjackPage:
    BET_MODE = "bet"
    PLAY_MODE = "play"
    RESULT_MODE = "result"
    RESET_MODE = "reset"
    BETS = (10, 25, 50, 100)
    ACTIONS = ("Hit", "Stand")

    def __init__(self, stats_store) -> None:
        self.stats_store = stats_store
        self.game = BlackjackGame()
        self.mode = self.BET_MODE
        self.selected_index = 0
        self.message = ""
        self._recorded = False

    def open(self) -> None:
        balance = self.stats_store.blackjack_stats()["balance"]
        self.game = BlackjackGame(balance)
        self.selected_index = 0
        self.message = "Choose bet"
        self._recorded = False
        self.mode = self.BET_MODE if self._available_bets() else self.RESET_MODE

    def handle_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if event.kind == EVENT_ESCAPE:
            return "back"
        if self.mode == self.RESET_MODE:
            if event.kind == EVENT_ENTER:
                stats = self.stats_store.reset_blackjack_balance()
                self.game.reset_balance()
                self.game.balance = stats["balance"]
                self.mode = self.BET_MODE
                self.selected_index = 0
                self.message = "Balance reset"
                return "changed"
            return "invalid"
        if self.mode == self.RESULT_MODE:
            if event.kind == EVENT_ENTER:
                self.mode = self.BET_MODE if self._available_bets() else self.RESET_MODE
                self.selected_index = 0
                self.message = "Choose bet"
                return "changed"
            return "unchanged"
        if event.kind == EVENT_UP:
            self._move_selection(-1)
            return "changed"
        if event.kind == EVENT_DOWN:
            self._move_selection(1)
            return "changed"
        if event.kind != EVENT_ENTER:
            return "invalid"
        if self.mode == self.BET_MODE:
            self._start_round(self._available_bets()[self.selected_index])
        else:
            self._play_action()
        return "changed"

    def render(self, display) -> bool:
        if self.mode == self.BET_MODE:
            bets = self._available_bets()
            lines = [
                ("> " if index == self.selected_index else "  ")
                + "Bet {0}".format(bet)
                for index, bet in enumerate(bets)
            ]
            return display.render_page(
                "BLACKJACK B:{0}".format(self.game.balance),
                lines,
                self.message or "w/s Enter Esc",
            )
        if self.mode == self.RESET_MODE:
            return display.render_page(
                "BLACKJACK B:{0}".format(self.game.balance),
                ["> Reset balance", "", "No real money"],
                "Enter Esc",
            )

        hide_dealer = self.mode == self.PLAY_MODE
        dealer_cards = self._cards(self.game.dealer, hide_second=hide_dealer)
        dealer_total = "?" if hide_dealer else str(hand_value(self.game.dealer))
        lines = [
            "Bet:{0} Balance:{1}".format(self.game.bet, self.game.balance),
            "You: " + self._cards(self.game.player),
            "Total: {0}".format(hand_value(self.game.player)),
            "Dealer: " + dealer_cards,
            "Dealer total: " + dealer_total,
        ]
        if self.mode == self.PLAY_MODE:
            footer = "{0} Hit  {1} Stand".format(
                ">" if self.selected_index == 0 else " ",
                ">" if self.selected_index == 1 else " ",
            )
        else:
            footer = self.message + " Enter:new"
        return display.render_page("BLACKJACK", lines, footer)

    def _start_round(self, bet: int) -> None:
        self.game.start_round(bet)
        self.selected_index = 0
        self._recorded = False
        if self.game.round_over:
            self._finish_round()
        else:
            self.mode = self.PLAY_MODE
            self.message = ""

    def _play_action(self) -> None:
        if self.selected_index == 0:
            self.game.hit()
        else:
            self.game.stand()
        if self.game.round_over:
            self._finish_round()

    def _finish_round(self) -> None:
        labels = {
            "blackjack": "Blackjack!",
            "win": "You win!",
            "loss": "You lose",
            "push": "Push",
        }
        self.message = labels[self.game.result]
        if not self._recorded:
            self.stats_store.record_blackjack(
                self.game.result, self.game.balance
            )
            self._recorded = True
        self.mode = self.RESULT_MODE

    def _move_selection(self, direction: int) -> None:
        count = len(self._available_bets()) if self.mode == self.BET_MODE else len(self.ACTIONS)
        self.selected_index = (self.selected_index + direction) % count

    def _available_bets(self):
        return [bet for bet in self.BETS if bet <= self.game.balance]

    @staticmethod
    def _cards(cards, hide_second: bool = False) -> str:
        labels = []
        for index, card in enumerate(cards):
            labels.append("??" if hide_second and index == 1 else card_label(card))
        return " ".join(labels)
