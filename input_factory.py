import sys
from typing import Callable, Optional

from input_cardkb import CardKBError, CardKBInputSource
from input_cli import CLIInputSource
from input_common import InputError, InputSource


INPUT_MODES = ("auto", "cardkb", "cli")


def create_input_source(
    mode: str,
    cardkb_factory: Optional[Callable[[], CardKBInputSource]] = None,
) -> InputSource:
    """Create and open the requested input source."""
    if mode == "cli":
        source = CLIInputSource()
        source.open()
        return source

    if mode not in INPUT_MODES:
        raise InputError("Unknown input mode: {0}".format(mode))

    factory = cardkb_factory or CardKBInputSource
    cardkb = factory()
    try:
        cardkb.open()
        return cardkb
    except CardKBError as exc:
        cardkb.close()
        if mode == "cardkb":
            raise
        print(
            "CardKB unavailable ({0}); falling back to CLI input.".format(exc),
            file=sys.stderr,
        )
        source = CLIInputSource()
        source.open()
        return source
