import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from input_cardkb import CardKBError, CardKBInputSource, decode_cardkb_code
from input_cli import CLIInputSource
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
    InputEvent,
    InputSource,
    command_for_event,
)
from input_factory import create_input_source


class FakeBus:
    def __init__(self, values):
        self.values = list(values)
        self.addresses = []
        self.closed = False

    def read_byte(self, address):
        self.addresses.append(address)
        return self.values.pop(0)

    def close(self):
        self.closed = True


class EventInput(InputSource):
    def __init__(self, events):
        self.events = iter(events)

    def read_event(self):
        return next(self.events)


class DecodeCardKBTest(unittest.TestCase):
    def test_zero_means_no_key(self):
        self.assertIsNone(decode_cardkb_code(0))

    def test_ascii_letters_and_numbers_are_characters(self):
        for code, character in ((97, "a"), (90, "Z"), (55, "7")):
            event = decode_cardkb_code(code)
            self.assertEqual(event.kind, EVENT_CHARACTER)
            self.assertEqual(event.character, character)

    def test_control_keys_are_separate_events(self):
        expected = {
            8: EVENT_BACKSPACE,
            9: EVENT_TAB,
            13: EVENT_ENTER,
            27: EVENT_ESCAPE,
        }
        for code, kind in expected.items():
            self.assertEqual(decode_cardkb_code(code).kind, kind)

    def test_cardkb_arrow_codes_map_to_navigation(self):
        expected = {
            180: (EVENT_LEFT, "back"),
            181: (EVENT_UP, "up"),
            182: (EVENT_DOWN, "down"),
            183: (EVENT_RIGHT, "select"),
        }
        for code, (kind, command) in expected.items():
            event = decode_cardkb_code(code)
            self.assertEqual(event.kind, kind)
            self.assertEqual(command_for_event(event), command)

    def test_unknown_special_code_is_safe(self):
        event = decode_cardkb_code(200)
        self.assertEqual(event.kind, EVENT_SPECIAL)
        self.assertEqual(event.code, 200)
        self.assertEqual(command_for_event(event), "invalid")

    def test_confirmation_characters_map_to_commands(self):
        self.assertEqual(command_for_event(decode_cardkb_code(ord("y"))), "yes")
        self.assertEqual(command_for_event(decode_cardkb_code(ord("Y"))), "yes")
        self.assertEqual(command_for_event(decode_cardkb_code(ord("n"))), "no")


class CardKBInputSourceTest(unittest.TestCase):
    def test_probe_polling_and_character_read(self):
        bus = FakeBus([0, 0, ord("k")])
        sleeps = []
        source = CardKBInputSource(
            bus_factory=lambda bus_number: bus,
            sleeper=lambda seconds: sleeps.append(seconds),
        )

        source.open()
        event = source.read_event()
        source.close()

        self.assertEqual(event.character, "k")
        self.assertEqual(bus.addresses, [0x5F, 0x5F, 0x5F])
        self.assertEqual(sleeps, [0.03])
        self.assertTrue(bus.closed)

    def test_key_during_probe_is_not_lost(self):
        bus = FakeBus([ord("4")])
        source = CardKBInputSource(bus_factory=lambda bus_number: bus)
        source.open()
        event = source.read_event()
        source.close()
        self.assertEqual(event.character, "4")

    def test_missing_cardkb_falls_back_only_in_auto_mode(self):
        def missing_bus(_bus_number):
            raise OSError("No such device")

        factory = lambda: CardKBInputSource(bus_factory=missing_bus)
        with redirect_stderr(io.StringIO()):
            fallback = create_input_source("auto", cardkb_factory=factory)
        self.assertIsInstance(fallback, CLIInputSource)
        fallback.close()

        with self.assertRaises(CardKBError):
            create_input_source("cardkb", cardkb_factory=factory)


class CardKBTextInputTest(unittest.TestCase):
    def test_ascii_backspace_and_enter_edit_a_line(self):
        source = EventInput(
            [
                InputEvent(EVENT_CHARACTER, "a", 97),
                InputEvent(EVENT_CHARACTER, "b", 98),
                InputEvent(EVENT_BACKSPACE, code=8),
                InputEvent(EVENT_CHARACTER, "2", 50),
                InputEvent(EVENT_ENTER, code=13),
            ]
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(source.read_line(), "a2")

    def test_escape_cancels_a_line(self):
        source = EventInput([InputEvent(EVENT_ESCAPE, code=27)])
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(source.read_line())


if __name__ == "__main__":
    unittest.main()
