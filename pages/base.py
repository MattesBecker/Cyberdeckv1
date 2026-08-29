from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from display import EpaperDisplay


class BasePage:
    key = ""
    title = ""
    lines: Sequence[str] = ()

    def render(self, display: "EpaperDisplay") -> bool:
        return display.render_page(self.title, self.lines)
