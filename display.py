import importlib
import sys
from pathlib import Path
from typing import Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from config import (
    DISPLAY_HEIGHT,
    DISPLAY_MODEL,
    DISPLAY_WIDTH,
    WAVESHARE_LIB_PATH,
)


MenuItem = Tuple[str, str]


class DisplayError(RuntimeError):
    """Raised when the display cannot be initialized or updated."""


class EpaperDisplay:
    """Render the UI and isolate all Waveshare-specific access."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT
        self.last_frame: Optional[bytes] = None
        self._epd = None
        self._initialized = False
        self._font = self._load_font(11)
        self._title_font = self._load_font(12, bold=True)

    @staticmethod
    def _load_font(size: int, bold: bool = False):
        filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        font_path = Path("/usr/share/fonts/truetype/dejavu") / filename
        try:
            return ImageFont.truetype(str(font_path), size)
        except (OSError, IOError):
            return ImageFont.load_default()

    def initialize(self) -> None:
        """Initialize the hardware once, or prepare terminal-only rendering."""
        if self._initialized:
            return

        if not self.enabled:
            self._initialized = True
            return

        library_path = str(WAVESHARE_LIB_PATH)
        if library_path not in sys.path:
            sys.path.append(library_path)

        try:
            driver = importlib.import_module(
                "waveshare_epd.{0}".format(DISPLAY_MODEL)
            )
        except ImportError as exc:
            raise DisplayError(
                "Waveshare module '{0}' could not be imported from {1}: {2}".format(
                    DISPLAY_MODEL, WAVESHARE_LIB_PATH, exc
                )
            ) from exc

        try:
            self._epd = driver.EPD()
            init_result = self._epd.init()
            if init_result not in (0, None):
                raise RuntimeError(
                    "Waveshare driver returned status {0}".format(init_result)
                )
            self._initialized = True
        except Exception as exc:
            self._epd = None
            raise DisplayError(
                "Failed to initialize e-paper display. "
                "Check SPI, wiring, and the Waveshare setup: {0}".format(exc)
            ) from exc

    def _new_image(self) -> Image.Image:
        return Image.new("1", (self.width, self.height), 1)

    def render_menu(
        self, items: Sequence[MenuItem], selected_index: int
    ) -> bool:
        """Render the main menu and refresh only when it changed."""
        try:
            image = self._new_image()
            draw = ImageDraw.Draw(image)
            draw.text((5, 3), "CYBERDECK", font=self._title_font, fill=0)

            y = 22
            preview_lines = ["CYBERDECK", ""]
            for index, (label, _page_key) in enumerate(items):
                prefix = "> " if index == selected_index else "  "
                line = prefix + label
                draw.text((5, y), line, font=self._font, fill=0)
                preview_lines.append(line)
                y += 16

            return self.refresh(image, preview_lines)
        except DisplayError:
            raise
        except Exception as exc:
            raise DisplayError("Failed to render the main menu: {0}".format(exc)) from exc

    def render_text(
        self,
        title: str,
        lines: Sequence[str],
        footer: Optional[str] = None,
    ) -> bool:
        """Render a simple title, body lines, and optional footer."""
        try:
            image = self._new_image()
            draw = ImageDraw.Draw(image)
            draw.text((5, 4), title, font=self._title_font, fill=0)

            y = 28
            for line in lines:
                draw.text((5, y), line, font=self._font, fill=0)
                y += 16

            preview_lines = [title, ""] + list(lines)
            if footer:
                draw.text(
                    (5, self.height - 16), footer, font=self._font, fill=0
                )
                preview_lines.extend(("", footer))

            return self.refresh(image, preview_lines)
        except DisplayError:
            raise
        except Exception as exc:
            raise DisplayError(
                "Failed to render page '{0}': {1}".format(title, exc)
            ) from exc

    def render_page(
        self, title: str, lines: Sequence[str], footer: str = "b: back"
    ) -> bool:
        return self.render_text(title, lines, footer)

    def refresh(
        self, image: Image.Image, preview_lines: Optional[Sequence[str]] = None
    ) -> bool:
        """Show a full frame. Return False when it matches the last frame."""
        if not self._initialized:
            raise DisplayError("Display must be initialized before rendering.")
        if image.size != (self.width, self.height):
            raise DisplayError(
                "Invalid frame size {0}; expected {1}x{2}.".format(
                    image.size, self.width, self.height
                )
            )

        monochrome = image.convert("1")
        frame_data = monochrome.tobytes()
        if frame_data == self.last_frame:
            return False

        if self.enabled:
            if self._epd is None:
                raise DisplayError("E-paper hardware is not available.")
            try:
                # The V3 driver converts this 250x122 landscape image to its
                # native 122x250 buffer orientation.
                buffer = self._epd.getbuffer(monochrome)
                self._epd.display(buffer)
            except Exception as exc:
                raise DisplayError(
                    "Failed to refresh e-paper display: {0}".format(exc)
                ) from exc
        else:
            self._print_preview(preview_lines or ("[image frame]",))

        self.last_frame = frame_data
        return True

    @staticmethod
    def _print_preview(lines: Sequence[str]) -> None:
        print("\n--- DISPLAY ---")
        for line in lines:
            print(line)
        print("---------------")

    def clear(self) -> bool:
        """Clear the screen, unless it is already blank."""
        return self.refresh(self._new_image(), ("[blank]",))

    def sleep(self) -> None:
        """Put initialized hardware into deep sleep."""
        if not self.enabled or self._epd is None:
            return
        try:
            self._epd.sleep()
        except Exception as exc:
            raise DisplayError(
                "Failed to put e-paper display to sleep: {0}".format(exc)
            ) from exc
