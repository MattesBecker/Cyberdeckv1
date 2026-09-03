import subprocess
import tempfile
import unittest
from pathlib import Path

from services.network_info import NetworkInfoService
from services.system_info import (
    PowerController,
    SystemActionError,
    SystemInfoService,
)


class Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class SystemInfoServiceTest(unittest.TestCase):
    def test_reads_proc_snapshot_without_psutil(self):
        with tempfile.TemporaryDirectory() as directory:
            proc_root = Path(directory)
            (proc_root / "uptime").write_text("8050.2 0.0\n", encoding="utf-8")
            (proc_root / "stat").write_text(
                "cpu 100 0 50 850 0 0 0 0\n", encoding="utf-8"
            )
            (proc_root / "meminfo").write_text(
                "MemTotal: 524288 kB\nMemAvailable: 131072 kB\n",
                encoding="utf-8",
            )

            def advance_cpu(_seconds):
                (proc_root / "stat").write_text(
                    "cpu 150 0 100 950 0 0 0 0\n", encoding="utf-8"
                )

            service = SystemInfoService(
                proc_root=proc_root,
                disk_path=proc_root,
                sleeper=advance_cpu,
            )
            info = service.read()

        self.assertEqual(info.uptime_seconds, 8050.2)
        self.assertEqual(info.cpu_percent, 50.0)
        self.assertEqual(info.memory_used_mb, 384)
        self.assertEqual(info.memory_total_mb, 512)
        self.assertGreater(info.disk_free_bytes, 0)

    def test_missing_proc_values_do_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            info = SystemInfoService(proc_root=missing).read()
        self.assertIsNone(info.uptime_seconds)
        self.assertIsNone(info.cpu_percent)
        self.assertIsNone(info.memory_used_mb)
        self.assertIsNone(info.memory_total_mb)


class NetworkInfoServiceTest(unittest.TestCase):
    def test_reads_nmcli_wifi_ipv4_and_signal(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            joined = " ".join(command)
            if "DEVICE,TYPE,STATE" in joined:
                return Completed(stdout="wlan0:wifi:connected\n")
            if "ACTIVE,SSID,SIGNAL" in joined:
                return Completed(stdout="yes:Deck\\:Net:73\n")
            if "IP4.ADDRESS" in joined:
                return Completed(stdout="192.168.4.23/24\n")
            raise AssertionError("Unexpected command: {0}".format(command))

        info = NetworkInfoService(runner=runner).read()
        self.assertEqual(info.ssid, "Deck:Net")
        self.assertEqual(info.ipv4, "192.168.4.23")
        self.assertEqual(info.signal_percent, 73)
        self.assertTrue(all(call[0][0] == "nmcli" for call in calls))
        self.assertTrue(all(call[1]["timeout"] == 3.0 for call in calls))

    def test_missing_nmcli_is_reported(self):
        def runner(_command, **_kwargs):
            raise FileNotFoundError

        info = NetworkInfoService(runner=runner).read()
        self.assertEqual(info.status, "nmcli unavailable")
        self.assertIsNone(info.ssid)

    def test_no_connected_wifi_is_reported(self):
        def runner(_command, **_kwargs):
            return Completed(stdout="wlan0:wifi:disconnected\n")

        info = NetworkInfoService(runner=runner).read()
        self.assertEqual(info.status, "No Wi-Fi connected")
        self.assertIsNone(info.ipv4)

    def test_ping_is_bounded_and_never_uses_a_shell(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return Completed(
                stdout="64 bytes from 1.1.1.1: time=24.3 ms\n"
            )

        result = NetworkInfoService(runner=runner).ping("1.1.1.1")
        self.assertTrue(result.success)
        self.assertEqual(result.latency_ms, 24.3)
        self.assertEqual(
            calls[0][0], ["ping", "-c", "1", "-W", "2", "1.1.1.1"]
        )
        self.assertEqual(calls[0][1]["timeout"], 4.0)
        self.assertNotIn("shell", calls[0][1])

    def test_invalid_ping_target_is_not_executed(self):
        def runner(_command, **_kwargs):
            raise AssertionError("runner must not be called")

        result = NetworkInfoService(runner=runner).ping("-c 99; reboot")
        self.assertFalse(result.success)
        self.assertEqual(result.message, "Invalid host")

    def test_ping_timeout_is_reported(self):
        def runner(command, **_kwargs):
            raise subprocess.TimeoutExpired(command, timeout=4)

        result = NetworkInfoService(runner=runner).ping("router")
        self.assertFalse(result.success)
        self.assertEqual(result.message, "Timed out")

    def test_unreachable_ping_is_reported(self):
        service = NetworkInfoService(
            runner=lambda _command, **_kwargs: Completed(returncode=1)
        )
        result = service.ping("router")
        self.assertFalse(result.success)
        self.assertEqual(result.message, "Unreachable")


class PowerControllerTest(unittest.TestCase):
    def test_shutdown_uses_argument_list_and_noninteractive_sudo(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return Completed()

        PowerController(runner=runner).execute("shutdown")
        self.assertEqual(
            calls[0][0], ["sudo", "-n", "shutdown", "-h", "now"]
        )
        self.assertNotIn("shell", calls[0][1])

    def test_rejected_power_command_is_reported(self):
        controller = PowerController(
            runner=lambda _command, **_kwargs: Completed(
                returncode=1, stderr="sudo: a password is required"
            )
        )
        with self.assertRaises(SystemActionError):
            controller.execute("reboot")


if __name__ == "__main__":
    unittest.main()
