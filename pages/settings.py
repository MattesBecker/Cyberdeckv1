from typing import List

from input_common import (
    EVENT_DOWN,
    EVENT_ENTER,
    EVENT_EOF,
    EVENT_ESCAPE,
    EVENT_LEFT,
    EVENT_RIGHT,
    EVENT_UP,
    InputEvent,
)
from settings_store import RuntimeSettings, SettingsError, SettingsStore

from .base import BasePage


class SettingsPage(BasePage):
    key = "settings"
    title = "SETTINGS"
    ITEMS = (
        "Bootscreen",
        "Boot duration",
        "Partial refresh",
        "Start screen",
        "Kiwix",
        "Dashboard WiFi",
        "Dashboard Tasks",
        "Dashboard Storage",
        "Back",
    )

    def __init__(self, store: SettingsStore, settings: RuntimeSettings) -> None:
        self.store = store
        self.settings = settings
        self.selected_index = 0
        self.list_offset = 0
        self._row_count = 5
        self.message = ""

    def open(self) -> None:
        self.settings = self.store.load()
        self.selected_index = 0
        self.list_offset = 0
        self.message = ""

    def handle_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if event.kind == EVENT_ESCAPE:
            return "back"
        if event.kind == EVENT_UP:
            self.selected_index = (self.selected_index - 1) % len(self.ITEMS)
            return "changed"
        if event.kind == EVENT_DOWN:
            self.selected_index = (self.selected_index + 1) % len(self.ITEMS)
            return "changed"
        if event.kind in (EVENT_ENTER, EVENT_RIGHT, EVENT_LEFT):
            if self.ITEMS[self.selected_index] == "Back":
                return "back"
            direction = -1 if event.kind == EVENT_LEFT else 1
            return "changed" if self._change(direction) else "unchanged"
        return "invalid"

    def _change(self, direction: int) -> bool:
        field = (
            "boot_enabled",
            "boot_duration",
            "partial_refresh_max",
            "start_screen",
            "kiwix_enabled",
            "dashboard_wifi",
            "dashboard_tasks",
            "dashboard_storage",
        )[self.selected_index]
        old = getattr(self.settings, field)
        if field == "boot_duration":
            value = round(max(0.0, min(10.0, old + (0.5 * direction))), 1)
        elif field == "partial_refresh_max":
            value = max(1, min(50, old + direction))
        elif field == "start_screen":
            value = "menu" if old == "dashboard" else "dashboard"
        else:
            value = not old
        if value == old:
            return False
        try:
            self.settings = self.store.update(self.settings, **{field: value})
            self.message = "Saved"
            return True
        except SettingsError:
            self.message = "Could not save"
            return True

    def render(self, display) -> bool:
        self._row_count = display.body_line_count
        self._keep_visible()
        labels = self._labels()
        end = min(self.list_offset + self._row_count, len(labels))
        lines: List[str] = []
        for index in range(self.list_offset, end):
            lines.append(("> " if index == self.selected_index else "  ") + labels[index])
        footer = self.message or "arrows/Enter  Esc"
        return display.render_page(self.title, lines, footer)

    def _labels(self) -> List[str]:
        yes_no = lambda value: "on" if value else "off"
        return [
            "Boot: " + yes_no(self.settings.boot_enabled),
            "Boot time: {0:.1f}s".format(self.settings.boot_duration),
            "Partial max: {0}".format(self.settings.partial_refresh_max),
            "Start: " + ("Dashboard" if self.settings.start_screen == "dashboard" else "Main Menu"),
            "Kiwix: " + yes_no(self.settings.kiwix_enabled),
            "Dash WiFi: " + yes_no(self.settings.dashboard_wifi),
            "Dash Tasks: " + yes_no(self.settings.dashboard_tasks),
            "Dash Storage: " + yes_no(self.settings.dashboard_storage),
            "Back",
        ]

    def _keep_visible(self) -> None:
        if self.selected_index < self.list_offset:
            self.list_offset = self.selected_index
        elif self.selected_index >= self.list_offset + self._row_count:
            self.list_offset = self.selected_index - self._row_count + 1
        self.list_offset = min(self.list_offset, max(0, len(self.ITEMS) - self._row_count))
