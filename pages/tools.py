from typing import List, Optional

from config import (
    FILE_VIEWER_MAX_BYTES,
    FILE_VIEWER_ROOTS,
    SSH_COMMAND_TIMEOUT,
    SSH_MAX_OUTPUT_CHARS,
    SSH_SHORTCUT_LIMIT,
    SSH_SHORTCUTS_FILE,
)
from input_common import (
    EVENT_BACKSPACE,
    EVENT_CHARACTER,
    EVENT_ENTER,
    EVENT_EOF,
    EVENT_ESCAPE,
    EVENT_TAB,
    EVENT_TEXT,
    InputEvent,
)

from services import (
    NetworkInfo,
    NetworkInfoService,
    PingResult,
    SystemInfo,
    SystemInfoService,
    Calculator,
    CalculatorError,
    FileViewerService,
    SSHShortcutService,
    SSHShortcutStore,
)

from .base import BasePage
from .file_viewer import FileViewerPage
from .ssh_shortcuts import SSHShortcutsPage


class ToolsPage(BasePage):
    key = "tools"
    title = "TOOLS"

    MENU_MODE = "menu"
    SYSTEM_MODE = "system"
    NETWORK_MODE = "network"
    PING_MODE = "ping"
    CONFIRM_MODE = "confirm"
    POWER_MODE = "power"
    CALCULATOR_MODE = "calculator"
    FILE_MODE = "file_viewer"
    SSH_MODE = "ssh_shortcuts"

    MENU_ITEMS = (
        "System info",
        "Network",
        "Reboot",
        "Shutdown",
        "Calculator",
        "File Viewer",
        "SSH Shortcuts",
    )

    def __init__(
        self,
        system_service: SystemInfoService,
        network_service: NetworkInfoService,
        calculator: Optional[Calculator] = None,
        file_page: Optional[FileViewerPage] = None,
        ssh_page: Optional[SSHShortcutsPage] = None,
    ) -> None:
        self.system_service = system_service
        self.network_service = network_service
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.system_info: Optional[SystemInfo] = None
        self.network_info: Optional[NetworkInfo] = None
        self.ping_result: Optional[PingResult] = None
        self.power_message = ""
        self._confirmation_action: Optional[str] = None
        self._pending_power_action: Optional[str] = None
        self.calculator = calculator or Calculator()
        self.file_page = file_page or FileViewerPage(
            FileViewerService(FILE_VIEWER_ROOTS, FILE_VIEWER_MAX_BYTES)
        )
        self.ssh_page = ssh_page or SSHShortcutsPage(
            SSHShortcutStore(SSH_SHORTCUTS_FILE, SSH_SHORTCUT_LIMIT),
            SSHShortcutService(
                timeout=SSH_COMMAND_TIMEOUT,
                max_output_chars=SSH_MAX_OUTPUT_CHARS,
            ),
        )
        self.calculator_buffer = ""
        self.calculator_expression = ""
        self.calculator_result = ""
        self.calculator_error = ""
        self.calculator_history: List[str] = []
        self.list_offset = 0
        self._row_count = 5

    def open_menu(self, reset_selection: bool = True) -> None:
        self.mode = self.MENU_MODE
        self.system_info = None
        self.network_info = None
        self.ping_result = None
        self.power_message = ""
        self._confirmation_action = None
        self._pending_power_action = None
        if reset_selection:
            self.selected_index = 0
            self.list_offset = 0

    def move_up(self) -> bool:
        if self.mode != self.MENU_MODE:
            return False
        self.selected_index = (self.selected_index - 1) % len(self.MENU_ITEMS)
        return True

    def move_down(self) -> bool:
        if self.mode != self.MENU_MODE:
            return False
        self.selected_index = (self.selected_index + 1) % len(self.MENU_ITEMS)
        return True

    def select(self) -> str:
        if self.mode == self.SYSTEM_MODE:
            self.show_system_info()
            return "changed"
        if self.mode in (self.NETWORK_MODE, self.PING_MODE):
            return "ping"
        if self.mode != self.MENU_MODE:
            return "unchanged"

        action = ("system", "network", "reboot", "shutdown", "calculator", "file", "ssh")[
            self.selected_index
        ]
        if action == "system":
            self.show_system_info()
            return "changed"
        if action == "network":
            self.show_network_info()
            return "changed"
        if action == "calculator":
            self.mode = self.CALCULATOR_MODE
            self.calculator_buffer = ""
            self.calculator_expression = ""
            self.calculator_result = ""
            self.calculator_error = ""
            return "changed"
        if action == "file":
            self.file_page.open()
            self.mode = self.FILE_MODE
            return "changed"
        if action == "ssh":
            self.ssh_page.open()
            self.mode = self.SSH_MODE
            return "changed"
        self.show_power_confirmation(action)
        return "changed"

    def show_system_info(self) -> None:
        self.system_info = self.system_service.read()
        self.mode = self.SYSTEM_MODE

    def show_network_info(self) -> None:
        self.network_info = self.network_service.read()
        self.mode = self.NETWORK_MODE

    def run_ping(self, target: str) -> None:
        self.ping_result = self.network_service.ping(target)
        self.mode = self.PING_MODE

    @property
    def is_confirming(self) -> bool:
        return (
            self.mode == self.CONFIRM_MODE
            and self._confirmation_action is not None
        )

    def show_power_confirmation(self, action: str) -> None:
        self._confirmation_action = action
        self._pending_power_action = None
        self.mode = self.CONFIRM_MODE

    def resolve_power_confirmation(
        self, confirmed: bool, simulated: bool
    ) -> Optional[str]:
        action = self._confirmation_action
        if not self.is_confirming or action is None:
            return None

        self._confirmation_action = None
        if not confirmed:
            self.mode = self.MENU_MODE
            return action

        label = "Reboot" if action == "reboot" else "Shutdown"
        self.mode = self.POWER_MODE
        if simulated:
            self.power_message = label + " simulated"
            self._pending_power_action = None
        else:
            self.power_message = label + " requested"
            self._pending_power_action = action
        return action

    def take_power_action(self) -> Optional[str]:
        action = self._pending_power_action
        self._pending_power_action = None
        return action

    def back_to_menu(self) -> bool:
        if self.mode == self.MENU_MODE:
            return False
        self.mode = self.MENU_MODE
        self._confirmation_action = None
        self._pending_power_action = None
        return True

    @property
    def handles_events(self) -> bool:
        return self.mode in (self.CALCULATOR_MODE, self.FILE_MODE, self.SSH_MODE)

    def handle_event(self, event: InputEvent) -> str:
        if self.mode == self.CALCULATOR_MODE:
            return self._handle_calculator_event(event)
        if self.mode == self.FILE_MODE:
            action = self.file_page.handle_event(event)
        elif self.mode == self.SSH_MODE:
            action = self.ssh_page.handle_event(event)
        else:
            return "unhandled"
        if action == "back":
            self.mode = self.MENU_MODE
            return "changed"
        return action

    def render(self, display) -> bool:
        if self.mode == self.SYSTEM_MODE:
            return display.render_page(
                "SYSTEM", self._system_lines(), "Enter: refresh  b"
            )
        if self.mode == self.NETWORK_MODE:
            return display.render_page(
                "NETWORK", self._network_lines(), "Enter: ping  b"
            )
        if self.mode == self.PING_MODE:
            return display.render_page(
                "PING", self._ping_lines(), "Enter: again  b"
            )
        if self.mode == self.CONFIRM_MODE:
            action = self._confirmation_action or "shutdown"
            label = "Reboot" if action == "reboot" else "Shutdown"
            return display.render_page(
                label.upper(), [label + " system?", "y / n"], "Esc: cancel"
            )
        if self.mode == self.POWER_MODE:
            return display.render_page(
                "SYSTEM", [self.power_message], "b: back"
            )
        if self.mode == self.CALCULATOR_MODE:
            lines = []
            if self.calculator_expression:
                lines.extend((self.calculator_expression, "= " + self.calculator_result))
            if self.calculator_error:
                lines.append(self.calculator_error)
            lines.extend(display.wrap_text("> " + self.calculator_buffer + "_")[-2:])
            return display.render_page("CALCULATOR", lines[-display.body_line_count:], "Enter:solve Esc:back")
        if self.mode == self.FILE_MODE:
            return self.file_page.render(display)
        if self.mode == self.SSH_MODE:
            return self.ssh_page.render(display)

        self._row_count = getattr(display, "body_line_count", 5)
        self._keep_selection_visible()
        end = min(self.list_offset + self._row_count, len(self.MENU_ITEMS))
        lines = []
        for index in range(self.list_offset, end):
            label = self.MENU_ITEMS[index]
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + label)
        return display.render_page("TOOLS", lines, "{0}/{1} Enter b".format(self.selected_index + 1, len(self.MENU_ITEMS)))

    def _handle_calculator_event(self, event: InputEvent) -> str:
        if event.kind == EVENT_EOF:
            return "quit"
        if event.kind == EVENT_ESCAPE:
            self.mode = self.MENU_MODE
            return "changed"
        if event.kind == EVENT_BACKSPACE:
            self.calculator_buffer = self.calculator_buffer[:-1]
            return "changed"
        if event.kind == EVENT_TAB:
            self.calculator_buffer += " "
            return "changed"
        if event.kind in (EVENT_CHARACTER, EVENT_TEXT) and event.character is not None:
            value = event.character
            if event.kind == EVENT_TEXT:
                self.calculator_buffer = value
            elif value in "0123456789.+-*/%^() ":
                self.calculator_buffer += value
            else:
                self.calculator_error = "Invalid character"
            return "changed"
        if event.kind != EVENT_ENTER:
            return "unchanged"
        expression = self.calculator_buffer.strip()
        try:
            value = self.calculator.calculate(expression)
            self.calculator_expression = expression
            self.calculator_result = self.calculator.format_result(value)
            self.calculator_history.insert(0, expression)
            self.calculator_history = self.calculator_history[:10]
            self.calculator_error = ""
            self.calculator_buffer = ""
        except CalculatorError as exc:
            self.calculator_error = str(exc)
        return "changed"

    def _keep_selection_visible(self) -> None:
        if self.selected_index < self.list_offset:
            self.list_offset = self.selected_index
        elif self.selected_index >= self.list_offset + self._row_count:
            self.list_offset = self.selected_index - self._row_count + 1
        self.list_offset = min(self.list_offset, max(0, len(self.MENU_ITEMS) - self._row_count))

    def _system_lines(self) -> List[str]:
        info = self.system_info
        if info is None:
            return ["System information unavailable"]
        cpu = "?" if info.cpu_percent is None else "{0:.0f}%".format(
            info.cpu_percent
        )
        if info.memory_used_mb is None or info.memory_total_mb is None:
            memory = "?"
        else:
            memory = "{0}/{1} MB".format(
                info.memory_used_mb, info.memory_total_mb
            )
        return [
            "Host: " + info.hostname,
            "Up: " + self._format_uptime(info.uptime_seconds),
            "CPU: " + cpu,
            "RAM: " + memory,
            "Disk: " + self._format_disk(info.disk_free_bytes),
        ]

    def _network_lines(self) -> List[str]:
        info = self.network_info
        if info is None:
            return ["Network information unavailable", "> Ping host"]
        signal = "?" if info.signal_percent is None else "{0}%".format(
            info.signal_percent
        )
        missing_ssid = (
            "not connected"
            if info.status == "No Wi-Fi connected"
            else "unavailable"
        )
        lines = [
            "SSID: " + (info.ssid or missing_ssid),
            "IP: " + (info.ipv4 or "unavailable"),
            "Signal: " + signal,
        ]
        if info.status:
            lines.append("Status: " + info.status)
        lines.append("> Ping host")
        return lines

    def _ping_lines(self) -> List[str]:
        result = self.ping_result
        if result is None:
            return ["No ping result"]
        lines = [result.target, ""]
        if result.success:
            lines.append("OK")
            if result.latency_ms is not None:
                lines.append("{0:g} ms".format(result.latency_ms))
        else:
            lines.extend(["FAILED", result.message or "Unknown error"])
        return lines

    @staticmethod
    def _format_uptime(seconds: Optional[float]) -> str:
        if seconds is None:
            return "?"
        minutes = int(seconds) // 60
        days, minutes = divmod(minutes, 24 * 60)
        hours, minutes = divmod(minutes, 60)
        if days:
            return "{0}d {1}h".format(days, hours)
        if hours:
            return "{0}h {1}m".format(hours, minutes)
        return "{0}m".format(minutes)

    @staticmethod
    def _format_disk(free_bytes: Optional[int]) -> str:
        if free_bytes is None:
            return "?"
        gigabytes = free_bytes / float(1024 ** 3)
        if gigabytes >= 10:
            return "{0:.0f} GB free".format(gigabytes)
        return "{0:.1f} GB free".format(gigabytes)
