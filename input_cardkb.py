import time
from typing import Callable, Optional

from config import (
    CARDKB_I2C_ADDRESS,
    CARDKB_I2C_BUS,
    CARDKB_POLL_INTERVAL,
)
from input_common import (
    EVENT_BACKSPACE,
    EVENT_CHARACTER,
    EVENT_DOWN,
    EVENT_ENTER,
    EVENT_ESCAPE,
    EVENT_LEFT,
    EVENT_RIGHT,
    EVENT_SPECIAL,
    EVENT_TAB,
    EVENT_UP,
    InputError,
    InputEvent,
    InputSource,
)


# Values emitted by the original M5Stack CardKB firmware key map.
CARDKB_LEFT = 180
CARDKB_UP = 181
CARDKB_DOWN = 182
CARDKB_RIGHT = 183


class CardKBError(InputError):
    """Raised when the CardKB cannot be initialized or read."""


def decode_cardkb_code(code: int) -> Optional[InputEvent]:
    """Decode one CardKB byte without depending on I2C hardware."""
    if not isinstance(code, int) or code < 0 or code > 255:
        return InputEvent(EVENT_SPECIAL, code=code)
    if code == 0:
        return None

    special_events = {
        8: EVENT_BACKSPACE,
        9: EVENT_TAB,
        10: EVENT_ENTER,
        13: EVENT_ENTER,
        27: EVENT_ESCAPE,
        127: EVENT_BACKSPACE,
        CARDKB_UP: EVENT_UP,
        CARDKB_DOWN: EVENT_DOWN,
        CARDKB_LEFT: EVENT_LEFT,
        CARDKB_RIGHT: EVENT_RIGHT,
    }
    event_kind = special_events.get(code)
    if event_kind is not None:
        return InputEvent(event_kind, code=code)
    if 32 <= code <= 126:
        return InputEvent(EVENT_CHARACTER, character=chr(code), code=code)
    return InputEvent(EVENT_SPECIAL, code=code)


class CardKBInputSource(InputSource):
    """Read CardKB key bytes from one SMBus device."""

    name = "cardkb"

    def __init__(
        self,
        bus_number: int = CARDKB_I2C_BUS,
        address: int = CARDKB_I2C_ADDRESS,
        poll_interval: float = CARDKB_POLL_INTERVAL,
        bus_factory: Optional[Callable[[int], object]] = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.bus_number = bus_number
        self.address = address
        self.poll_interval = poll_interval
        self._bus_factory = bus_factory or self._default_bus_factory
        self._sleeper = sleeper
        self._bus = None
        self._pending_code: Optional[int] = None

    @staticmethod
    def _default_bus_factory(bus_number: int):
        try:
            from smbus2 import SMBus
        except ImportError:
            try:
                from smbus import SMBus
            except ImportError as exc:
                raise CardKBError(
                    "Neither smbus2 nor smbus is installed. Install "
                    "python3-smbus or the smbus2 Python package."
                ) from exc
        return SMBus(bus_number)

    def open(self) -> None:
        if self._bus is not None:
            return
        try:
            self._bus = self._bus_factory(self.bus_number)
            probe_value = self._read_byte()
        except CardKBError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise CardKBError(
                "CardKB was not found on I2C bus {0} at 0x{1:02X}: {2}".format(
                    self.bus_number, self.address, exc
                )
            ) from exc

        if probe_value:
            self._pending_code = probe_value

    def close(self) -> None:
        bus = self._bus
        self._bus = None
        self._pending_code = None
        if bus is None:
            return
        close_method = getattr(bus, "close", None)
        if close_method is not None:
            try:
                close_method()
            except Exception:
                pass

    def read_event(self) -> InputEvent:
        if self._bus is None:
            raise CardKBError("CardKB input has not been opened.")

        while True:
            if self._pending_code is not None:
                code = self._pending_code
                self._pending_code = None
            else:
                code = self._read_byte()
            event = decode_cardkb_code(code)
            if event is not None:
                return event
            self._sleeper(self.poll_interval)

    def _read_byte(self) -> int:
        if self._bus is None:
            raise CardKBError("CardKB input has not been opened.")
        try:
            value = self._bus.read_byte(self.address)
        except Exception as exc:
            raise CardKBError(
                "Could not read CardKB on I2C bus {0} at 0x{1:02X}: {2}".format(
                    self.bus_number, self.address, exc
                )
            ) from exc
        if not isinstance(value, int) or value < 0 or value > 255:
            raise CardKBError(
                "CardKB returned an invalid byte: {0}".format(value)
            )
        return value
