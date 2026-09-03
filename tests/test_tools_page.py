import unittest

from pages.tools import ToolsPage
from services import NetworkInfo, PingResult, SystemInfo


class FakeSystemService:
    def __init__(self):
        self.read_count = 0

    def read(self):
        self.read_count += 1
        return SystemInfo(
            hostname="cyberdeck",
            uptime_seconds=8050,
            cpu_percent=8.2,
            memory_used_mb=72,
            memory_total_mb=512,
            disk_free_bytes=41 * 1024 ** 3,
        )


class FakeNetworkService:
    def __init__(self):
        self.targets = []

    def read(self):
        return NetworkInfo("DeckNet", "192.168.1.20", 77)

    def ping(self, target):
        self.targets.append(target)
        return PingResult(target, True, latency_ms=12.5)


class FakeDisplay:
    def __init__(self):
        self.last = None

    def render_page(self, title, lines, footer):
        self.last = (title, list(lines), footer)
        return True


class ToolsPageTest(unittest.TestCase):
    def setUp(self):
        self.system = FakeSystemService()
        self.network = FakeNetworkService()
        self.page = ToolsPage(self.system, self.network)
        self.display = FakeDisplay()

    def test_main_menu_navigation(self):
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "TOOLS")
        self.assertEqual(self.display.last[1][0], "> System info")
        self.page.move_down()
        self.page.render(self.display)
        self.assertEqual(self.display.last[1][1], "> Network")

    def test_system_info_reads_only_when_opened_or_refreshed(self):
        self.assertEqual(self.system.read_count, 0)
        self.assertEqual(self.page.select(), "changed")
        self.assertEqual(self.system.read_count, 1)
        self.page.render(self.display)
        self.assertEqual(
            self.display.last[1],
            [
                "Host: cyberdeck",
                "Up: 2h 14m",
                "CPU: 8%",
                "RAM: 72/512 MB",
                "Disk: 41 GB free",
            ],
        )
        self.page.select()
        self.assertEqual(self.system.read_count, 2)

    def test_network_and_ping_views(self):
        self.page.selected_index = 1
        self.assertEqual(self.page.select(), "changed")
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "NETWORK")
        self.assertIn("SSID: DeckNet", self.display.last[1])
        self.assertEqual(self.page.select(), "ping")
        self.page.run_ping("router")
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "PING")
        self.assertEqual(self.display.last[1], ["router", "", "OK", "12.5 ms"])

    def test_power_confirmation_is_rendered(self):
        self.page.selected_index = 3
        self.assertEqual(self.page.select(), "changed")
        self.assertTrue(self.page.is_confirming)
        self.page.render(self.display)
        self.assertEqual(self.display.last[0], "SHUTDOWN")
        self.assertEqual(
            self.display.last[1], ["Shutdown system?", "y / n"]
        )

    def test_no_cancels_power_confirmation(self):
        self.page.show_power_confirmation("shutdown")
        self.assertEqual(
            self.page.resolve_power_confirmation(False, simulated=False),
            "shutdown",
        )
        self.assertEqual(self.page.mode, self.page.MENU_MODE)
        self.assertIsNone(self.page.take_power_action())

    def test_no_display_power_confirmation_has_no_pending_action(self):
        self.page.show_power_confirmation("reboot")
        self.page.resolve_power_confirmation(True, simulated=True)
        self.assertIsNone(self.page.take_power_action())
        self.page.render(self.display)
        self.assertIn("simulated", self.display.last[1][0])

    def test_real_power_confirmation_is_consumed_once(self):
        self.page.show_power_confirmation("shutdown")
        self.page.resolve_power_confirmation(True, simulated=False)
        self.assertEqual(self.page.take_power_action(), "shutdown")
        self.assertIsNone(self.page.take_power_action())

    def test_back_returns_to_tools_menu_before_main_menu(self):
        self.page.show_network_info()
        self.assertTrue(self.page.back_to_menu())
        self.assertEqual(self.page.mode, self.page.MENU_MODE)
        self.assertFalse(self.page.back_to_menu())


if __name__ == "__main__":
    unittest.main()
