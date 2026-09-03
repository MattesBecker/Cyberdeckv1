from typing import List, Optional

from services import (
    NetworkInfo,
    NetworkInfoService,
    PingResult,
    SystemInfo,
    SystemInfoService,
)

from .base import BasePage


class ToolsPage(BasePage):
    key = "tools"
    title = "TOOLS"

    MENU_MODE = "menu"
    SYSTEM_MODE = "system"
    NETWORK_MODE = "network"
    PING_MODE = "ping"
    POWER_MODE = "power"

    MENU_ITEMS = ("System info", "Network", "Reboot", "Shutdown")

    def __init__(
        self,
        system_service: SystemInfoService,
        network_service: NetworkInfoService,
    ) -> None:
        self.system_service = system_service
        self.network_service = network_service
        self.mode = self.MENU_MODE
        self.selected_index = 0
        self.system_info: Optional[SystemInfo] = None
        self.network_info: Optional[NetworkInfo] = None
        self.ping_result: Optional[PingResult] = None
        self.power_message = ""
        self._pending_power_action: Optional[str] = None

    def open_menu(self, reset_selection: bool = True) -> None:
        self.mode = self.MENU_MODE
        self.system_info = None
        self.network_info = None
        self.ping_result = None
        self.power_message = ""
        self._pending_power_action = None
        if reset_selection:
            self.selected_index = 0

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

        action = ("system", "network", "reboot", "shutdown")[
            self.selected_index
        ]
        if action == "system":
            self.show_system_info()
            return "changed"
        if action == "network":
            self.show_network_info()
            return "changed"
        return action

    def show_system_info(self) -> None:
        self.system_info = self.system_service.read()
        self.mode = self.SYSTEM_MODE

    def show_network_info(self) -> None:
        self.network_info = self.network_service.read()
        self.mode = self.NETWORK_MODE

    def run_ping(self, target: str) -> None:
        self.ping_result = self.network_service.ping(target)
        self.mode = self.PING_MODE

    def confirm_power_action(self, action: str, simulated: bool) -> None:
        label = "Reboot" if action == "reboot" else "Shutdown"
        self.mode = self.POWER_MODE
        if simulated:
            self.power_message = label + " simulated"
            self._pending_power_action = None
        else:
            self.power_message = label + " requested"
            self._pending_power_action = action

    def take_power_action(self) -> Optional[str]:
        action = self._pending_power_action
        self._pending_power_action = None
        return action

    def back_to_menu(self) -> bool:
        if self.mode == self.MENU_MODE:
            return False
        self.mode = self.MENU_MODE
        self._pending_power_action = None
        return True

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
        if self.mode == self.POWER_MODE:
            return display.render_page(
                "SYSTEM", [self.power_message], "b: back"
            )

        lines = []
        for index, label in enumerate(self.MENU_ITEMS):
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + label)
        return display.render_page("TOOLS", lines, "w/s  Enter  b")

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
