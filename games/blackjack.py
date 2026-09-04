import random
from typing import List, Optional, Sequence, Tuple


Card = Tuple[str, str]
RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS = ("S", "H", "D", "C")


def card_label(card: Card) -> str:
    return "".join(card)


def hand_value(cards: Sequence[Card]) -> int:
    total = 0
    aces = 0
    for rank, _suit in cards:
        if rank == "A":
            total += 11
            aces += 1
        elif rank in ("J", "Q", "K"):
            total += 10
        else:
            total += int(rank)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_blackjack(cards: Sequence[Card]) -> bool:
    return len(cards) == 2 and hand_value(cards) == 21


class BlackjackGame:
    START_BALANCE = 1000

    def __init__(self, balance: int = START_BALANCE, rng=None) -> None:
        self.rng = rng or random.Random()
        self.balance = max(0, int(balance))
        self.deck: List[Card] = []
        self.player: List[Card] = []
        self.dealer: List[Card] = []
        self.bet = 0
        self.result: Optional[str] = None

    @property
    def round_over(self) -> bool:
        return self.result is not None

    def start_round(self, bet: int, deck: Optional[Sequence[Card]] = None) -> None:
        if self.round_over is False and (self.player or self.dealer):
            raise ValueError("Round already active")
        if bet <= 0 or bet > self.balance:
            raise ValueError("Invalid bet")
        if deck is None:
            next_deck = [(rank, suit) for suit in SUITS for rank in RANKS]
            self.rng.shuffle(next_deck)
        else:
            next_deck = list(deck)
        if len(next_deck) < 4:
            raise ValueError("Deck does not contain enough cards")
        self.bet = int(bet)
        self.balance -= self.bet
        self.result = None
        self.player = []
        self.dealer = []
        self.deck = next_deck
        self.player.append(self._draw())
        self.dealer.append(self._draw())
        self.player.append(self._draw())
        self.dealer.append(self._draw())
        player_blackjack = is_blackjack(self.player)
        dealer_blackjack = is_blackjack(self.dealer)
        if player_blackjack and dealer_blackjack:
            self._finish("push")
        elif player_blackjack:
            self._finish("blackjack")
        elif dealer_blackjack:
            self._finish("loss")

    def hit(self) -> Card:
        if self.round_over or not self.player:
            raise ValueError("No active round")
        card = self._draw()
        self.player.append(card)
        if hand_value(self.player) > 21:
            self._finish("loss")
        return card

    def stand(self) -> str:
        if self.round_over or not self.player:
            raise ValueError("No active round")
        while hand_value(self.dealer) < 17:
            self.dealer.append(self._draw())
        player_total = hand_value(self.player)
        dealer_total = hand_value(self.dealer)
        if dealer_total > 21 or player_total > dealer_total:
            self._finish("win")
        elif player_total < dealer_total:
            self._finish("loss")
        else:
            self._finish("push")
        return self.result or "push"

    def reset_balance(self) -> int:
        self.balance = self.START_BALANCE
        self.player = []
        self.dealer = []
        self.bet = 0
        self.result = None
        return self.balance

    def _draw(self) -> Card:
        if not self.deck:
            raise ValueError("Deck is empty")
        return self.deck.pop(0)

    def _finish(self, result: str) -> None:
        if result not in ("blackjack", "win", "loss", "push"):
            raise ValueError("Unknown result")
        if result == "blackjack":
            self.balance += (self.bet * 5) // 2
        elif result == "win":
            self.balance += self.bet * 2
        elif result == "push":
            self.balance += self.bet
        self.balance = max(0, self.balance)
        self.result = result
