import importlib
import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from config import (
    DISPLAY_HEIGHT,
    DISPLAY_MODEL,
    DISPLAY_WIDTH,
    PARTIAL_REFRESH_LIMIT,
    WAVESHARE_LIB_PATH,
)


MenuItem = Tuple[str, str]
logger = logging.getLogger(__name__)


class DisplayError(RuntimeError):
    """Raised when the display cannot be initialized or updated."""


class EpaperDisplay:
    """Render the UI and isolate all Waveshare-specific access."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT
        self.last_frame: Optional[bytes] = None
        self.partial_refresh_count = 0
        self.partial_refresh_limit = PARTIAL_REFRESH_LIMIT
        self.partial_ready = False
        self._force_next_full_refresh = False
        self.body_line_count = 5
        self._epd = None
        self._initialized = False
        self._font = self._load_font(11)
        self._mono_font = self._load_font(11, monospace=True)
        self._title_font = self._load_font(12, bold=True)
        self._measure_draw = ImageDraw.Draw(self._new_image())
        grid_glyphs = "[]|.XO#F*0123456789 "
        widest_grid_glyph = max(
            self._text_width(character, self._mono_font)
            for character in grid_glyphs
        )
        self._grid_cell_width = min(
            widest_grid_glyph,
            (self.width - 10) // 31,
        )

    @staticmethod
    def _load_font(size: int, bold: bool = False, monospace: bool = False):
        family = "DejaVuSansMono" if monospace else "DejaVuSans"
        filename = family + ("-Bold.ttf" if bold else ".ttf")
        font_path = Path("/usr/share/fonts/truetype/dejavu") / filename
        try:
            return ImageFont.truetype(str(font_path), size)
        except (OSError, IOError):
            try:
                return ImageFont.truetype(filename, size)
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

    def show_boot_screen(self, logo_path: Path) -> bool:
        """Render one centered monochrome boot frame with a text fallback."""
        image = self._new_image()
        preview_lines = ["CYBERDECK", "Starting..."]

        try:
            with Image.open(str(logo_path)) as source:
                source.load()
                rgba_logo = source.convert("RGBA")
            white_background = Image.new(
                "RGBA", rgba_logo.size, (255, 255, 255, 255)
            )
            white_background.alpha_composite(rgba_logo)
            logo = white_background.convert("L")
            resampling = getattr(Image, "Resampling", Image)
            logo.thumbnail(
                (max(1, self.width - 20), max(1, self.height - 20)),
                resample=resampling.LANCZOS,
            )
            dither = getattr(Image, "Dither", Image)
            logo = logo.convert("1", dither=dither.NONE)
            position = (
                (self.width - logo.width) // 2,
                (self.height - logo.height) // 2,
            )
            image.paste(logo, position)
            preview_lines = ["[boot logo]"]
        except Exception as exc:
            logger.warning(
                "Boot logo unavailable at %s; using text fallback: %s",
                logo_path,
                exc,
            )
            draw = ImageDraw.Draw(image)
            title = "CYBERDECK"
            subtitle = "STARTING"
            title_box = draw.textbbox((0, 0), title, font=self._title_font)
            subtitle_box = draw.textbbox((0, 0), subtitle, font=self._font)
            draw.text(
                ((self.width - (title_box[2] - title_box[0])) // 2, 42),
                title,
                font=self._title_font,
                fill=0,
            )
            draw.text(
                ((self.width - (subtitle_box[2] - subtitle_box[0])) // 2, 65),
                subtitle,
                font=self._font,
                fill=0,
            )

        return self.refresh_full(image, preview_lines=preview_lines)

    def request_full_refresh(self) -> None:
        """Force the next rendered frame to refresh fully, even if unchanged."""
        self._force_next_full_refresh = True

    def render_menu(
        self, items: Sequence[MenuItem], selected_index: int
    ) -> bool:
        """Render the main menu and refresh only when it changed."""
        try:
            image = self._new_image()
            draw = ImageDraw.Draw(image)
            draw.text((5, 3), "CYBERDECK", font=self._title_font, fill=0)

            visible_count = self.body_line_count
            offset = min(
                max(0, selected_index - visible_count + 1),
                max(0, len(items) - visible_count),
            )
            y = 22
            preview_lines = ["CYBERDECK", ""]
            for index in range(offset, min(offset + visible_count, len(items))):
                label, _page_key = items[index]
                prefix = "> " if index == selected_index else "  "
                line = prefix + label
                draw.text((5, y), line, font=self._font, fill=0)
                preview_lines.append(line)
                y += 16

            return self.refresh(image, preview_lines=preview_lines)
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
            visible_title = self.truncate_text(title, font=self._title_font)
            visible_lines = [
                self.truncate_text(line)
                for line in list(lines)[: self.body_line_count]
            ]
            draw.text((5, 4), visible_title, font=self._title_font, fill=0)

            y = 28
            for line in visible_lines:
                draw.text((5, y), line, font=self._font, fill=0)
                y += 16

            preview_lines = [visible_title, ""] + visible_lines
            if footer:
                visible_footer = self.truncate_text(footer)
                draw.text(
                    (5, self.height - 16),
                    visible_footer,
                    font=self._font,
                    fill=0,
                )
                preview_lines.extend(("", visible_footer))

            return self.refresh(image, preview_lines=preview_lines)
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

    def render_grid_page(
        self, title: str, lines: Sequence[str], footer: str = "b: back"
    ) -> bool:
        """Render fixed-width rows for game boards and other text grids."""
        try:
            image = self._new_image()
            draw = ImageDraw.Draw(image)
            visible_title = self.truncate_text(title, font=self._title_font)
            visible_lines = [
                self._truncate_grid_text(line)
                for line in list(lines)[: self.body_line_count]
            ]
            draw.text((5, 4), visible_title, font=self._title_font, fill=0)

            y = 28
            for line in visible_lines:
                self._draw_grid_text(draw, 5, y, line)
                y += 16

            visible_footer = self.truncate_text(footer)
            draw.text(
                (5, self.height - 16),
                visible_footer,
                font=self._font,
                fill=0,
            )
            preview_lines = [visible_title, ""] + visible_lines
            preview_lines.extend(("", visible_footer))
            return self.refresh(image, preview_lines=preview_lines)
        except DisplayError:
            raise
        except Exception as exc:
            raise DisplayError(
                "Failed to render grid page '{0}': {1}".format(title, exc)
            ) from exc

    def _truncate_grid_text(self, text: str) -> str:
        max_characters = (self.width - 10) // self._grid_cell_width
        if len(text) <= max_characters:
            return text
        if max_characters <= 3:
            return "." * max_characters
        return text[: max_characters - 3].rstrip() + "..."

    def _draw_grid_text(
        self, draw: ImageDraw.ImageDraw, x: int, y: int, text: str
    ) -> None:
        for column, character in enumerate(text):
            draw.text(
                (x + column * self._grid_cell_width, y),
                character,
                font=self._mono_font,
                fill=0,
            )

    def truncate_text(
        self,
        text: str,
        max_width: Optional[int] = None,
        font=None,
    ) -> str:
        """Fit one line to the display using a simple ASCII ellipsis."""
        available_width = max_width or (self.width - 10)
        selected_font = font or self._font
        if self._text_width(text, selected_font) <= available_width:
            return text

        suffix = "..."
        low = 0
        high = len(text)
        while low < high:
            middle = (low + high + 1) // 2
            candidate = text[:middle].rstrip() + suffix
            if self._text_width(candidate, selected_font) <= available_width:
                low = middle
            else:
                high = middle - 1
        return text[:low].rstrip() + suffix

    def wrap_text(
        self, text: str, max_width: Optional[int] = None
    ) -> List[str]:
        """Wrap plain text to the pixel width of the body font."""
        available_width = max_width or (self.width - 10)
        wrapped: List[str] = []

        for paragraph in text.split("\n"):
            words = paragraph.split()
            if not words:
                wrapped.append("")
                continue

            current = ""
            for word in words:
                parts = self._split_long_word(word, available_width)
                for part_index, part in enumerate(parts):
                    candidate = (current + " " + part).strip()
                    if self._text_width(candidate, self._font) <= available_width:
                        current = candidate
                        continue

                    if current:
                        wrapped.append(current)
                    current = part

                    if part_index < len(parts) - 1:
                        wrapped.append(current)
                        current = ""
            if current:
                wrapped.append(current)

        return wrapped or [""]

    def _split_long_word(self, word: str, max_width: int) -> List[str]:
        if self._text_width(word, self._font) <= max_width:
            return [word]

        parts = []
        remaining = word
        while remaining:
            low = 1
            high = len(remaining)
            while low < high:
                middle = (low + high + 1) // 2
                if self._text_width(remaining[:middle], self._font) <= max_width:
                    low = middle
                else:
                    high = middle - 1
            parts.append(remaining[:low])
            remaining = remaining[low:]
        return parts

    def _text_width(self, text: str, font) -> int:
        box = self._measure_draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]

    def refresh(
        self,
        image: Image.Image,
        mode: str = "auto",
        preview_lines: Optional[Sequence[str]] = None,
    ) -> bool:
        """Refresh a changed frame using the requested strategy.

        Identical frames are deliberately skipped in every mode, including an
        explicit full refresh, because no visible pixels would change.
        """
        if mode not in ("auto", "full", "partial"):
            raise ValueError(
                "Invalid refresh mode '{0}'; use auto, full, or partial.".format(
                    mode
                )
            )

        monochrome, frame_data = self._prepare_frame(image)
        force_full = self._force_next_full_refresh
        self._force_next_full_refresh = False
        if force_full:
            mode = "full"
        if frame_data == self.last_frame and not force_full:
            logger.debug("Skipping refresh: frame unchanged")
            return False

        if mode == "full":
            return self._perform_full_refresh(
                monochrome, frame_data, preview_lines
            )
        if mode == "partial":
            return self._perform_partial_refresh(
                monochrome, frame_data, preview_lines
            )

        if (
            self.last_frame is None
            or self.partial_refresh_count >= self.partial_refresh_limit
        ):
            return self._perform_full_refresh(
                monochrome, frame_data, preview_lines
            )
        return self._perform_partial_refresh(
            monochrome, frame_data, preview_lines
        )

    def refresh_full(
        self,
        image: Image.Image,
        preview_lines: Optional[Sequence[str]] = None,
    ) -> bool:
        """Request a full refresh; unchanged frames are still skipped."""
        return self.refresh(image, mode="full", preview_lines=preview_lines)

    def refresh_partial(
        self,
        image: Image.Image,
        preview_lines: Optional[Sequence[str]] = None,
    ) -> bool:
        """Request a partial refresh with a safe full-refresh fallback."""
        return self.refresh(image, mode="partial", preview_lines=preview_lines)

    def _prepare_frame(self, image: Image.Image) -> Tuple[Image.Image, bytes]:
        if not self._initialized:
            raise DisplayError("Display must be initialized before rendering.")
        if image.size != (self.width, self.height):
            raise DisplayError(
                "Invalid frame size {0}; expected {1}x{2}.".format(
                    image.size, self.width, self.height
                )
            )

        monochrome = image if image.mode == "1" else image.convert("1")
        return monochrome, monochrome.tobytes()

    def _perform_full_refresh(
        self,
        image: Image.Image,
        frame_data: bytes,
        preview_lines: Optional[Sequence[str]],
    ) -> bool:
        logger.debug("Full refresh")

        if self.enabled:
            if self._epd is None:
                raise DisplayError("E-paper hardware is not available.")
            try:
                # The V3 driver rotates this 250x122 landscape frame into its
                # native 122x250 buffer orientation.
                buffer = self._epd.getbuffer(image)
                self._epd.display(buffer)
            except Exception as exc:
                self.partial_ready = False
                raise DisplayError(
                    "Failed to perform full e-paper refresh: {0}".format(exc)
                ) from exc

            # display() has successfully made this frame visible. The V3
            # baseline call then mirrors it into both display RAM planes, as
            # required by Waveshare before displayPartial().
            self.last_frame = frame_data
            self.partial_refresh_count = 0
            self.partial_ready = False
            try:
                self._epd.displayPartBaseImage(buffer)
            except Exception as exc:
                raise DisplayError(
                    "Full refresh succeeded, but preparing the V3 partial "
                    "refresh baseline failed: {0}".format(exc)
                ) from exc
            self.partial_ready = True
        else:
            self._print_preview(preview_lines or ("[image frame]",))
            self.last_frame = frame_data
            self.partial_refresh_count = 0
            self.partial_ready = True

        return True

    def _perform_partial_refresh(
        self,
        image: Image.Image,
        frame_data: bytes,
        preview_lines: Optional[Sequence[str]],
    ) -> bool:
        if self.last_frame is None or not self.partial_ready:
            logger.warning(
                "Partial refresh baseline unavailable, using full refresh"
            )
            return self._perform_full_refresh(
                image, frame_data, preview_lines
            )

        if not self.enabled:
            self._print_preview(preview_lines or ("[image frame]",))
            self.last_frame = frame_data
            self.partial_refresh_count += 1
            logger.debug(
                "Partial refresh %d/%d",
                self.partial_refresh_count,
                self.partial_refresh_limit,
            )
            return True

        if self._epd is None:
            raise DisplayError("E-paper hardware is not available.")

        try:
            buffer = self._epd.getbuffer(image)
            self._epd.displayPartial(buffer)
        except Exception as partial_error:
            self.partial_ready = False
            logger.warning(
                "Partial refresh failed, falling back to full: %s",
                partial_error,
            )
            try:
                return self._perform_full_refresh(
                    image, frame_data, preview_lines
                )
            except DisplayError as full_error:
                raise DisplayError(
                    "Partial refresh failed ({0}); full-refresh fallback "
                    "also failed ({1}).".format(partial_error, full_error)
                ) from partial_error

        self.last_frame = frame_data
        self.partial_refresh_count += 1
        logger.debug(
            "Partial refresh %d/%d",
            self.partial_refresh_count,
            self.partial_refresh_limit,
        )
        return True

    @staticmethod
    def _print_preview(lines: Sequence[str]) -> None:
        print("\n--- DISPLAY ---")
        for line in lines:
            print(line)
        print("---------------")

    def clear(self) -> bool:
        """Clear the screen, unless it is already blank."""
        return self.refresh_full(
            self._new_image(), preview_lines=("[blank]",)
        )

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
