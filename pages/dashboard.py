from datetime import datetime
from typing import Callable, Optional

from services import NetworkInfoService, SystemInfoService
from settings_store import RuntimeSettings
from tasks_store import TasksStore, TasksStoreError

from .base import BasePage


class DashboardPage(BasePage):
    key = "dashboard"
    title = "CYBERDECK"

    def __init__(
        self,
        tasks_store: TasksStore,
        network_service: NetworkInfoService,
        system_service: SystemInfoService,
        settings: RuntimeSettings,
        wiki_ready: Callable[[], bool] = lambda: False,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.tasks_store = tasks_store
        self.network_service = network_service
        self.system_service = system_service
        self.settings = settings
        self._wiki_ready = wiki_ready
        self._clock = clock
        self.lines = []

    def open(self, settings: Optional[RuntimeSettings] = None) -> None:
        if settings is not None:
            self.settings = settings
        now = self._clock()
        self.lines = [now.strftime("%H:%M   %d.%m.")]
        if self.settings.dashboard_wifi:
            network = self.network_service.read()
            self.lines.append("WiFi: " + (network.ssid or "offline"))
            if network.ipv4 and len(self.lines) < 4:
                self.lines.append("IP: " + network.ipv4)
        if self.settings.dashboard_tasks:
            try:
                count = sum(1 for task in self.tasks_store.list_tasks() if not task.done)
                self.lines.append("Tasks: {0} open".format(count))
            except TasksStoreError:
                self.lines.append("Tasks: unavailable")
        wiki = "disabled" if not self.settings.kiwix_enabled else (
            "ready" if self._wiki_ready() else "not installed"
        )
        self.lines.append("Wiki: " + wiki)
        if self.settings.dashboard_storage and len(self.lines) < 5:
            info = self.system_service.read()
            if info.disk_free_bytes is not None:
                self.lines.append(
                    "Free: {0:.1f} GB".format(info.disk_free_bytes / float(1024 ** 3))
                )

    def render(self, display) -> bool:
        return display.render_page(self.title, self.lines[:5], "Enter: Menu")
