import ipaddress
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, List, Optional


PING_TIME_PATTERN = re.compile(r"time[=<]([0-9]+(?:\.[0-9]+)?)\s*ms")
HOST_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")


@dataclass(frozen=True)
class NetworkInfo:
    ssid: Optional[str]
    ipv4: Optional[str]
    signal_percent: Optional[int]
    status: Optional[str] = None


@dataclass(frozen=True)
class PingResult:
    target: str
    success: bool
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class NetworkCommandError(RuntimeError):
    pass


class NetworkInfoService:
    """Read Wi-Fi details with nmcli and run bounded single pings."""

    def __init__(
        self,
        runner: Callable = subprocess.run,
        command_timeout: float = 3.0,
        ping_timeout: float = 4.0,
    ) -> None:
        self._runner = runner
        self.command_timeout = command_timeout
        self.ping_timeout = ping_timeout

    def read(self) -> NetworkInfo:
        try:
            device = self._connected_wifi_device()
        except NetworkCommandError as exc:
            return NetworkInfo(None, None, None, str(exc))
        if device is None:
            return NetworkInfo(None, None, None, "No Wi-Fi connected")

        ssid = None
        signal = None
        ipv4 = None
        try:
            ssid, signal = self._read_active_wifi(device)
        except NetworkCommandError:
            pass
        try:
            ipv4 = self._read_ipv4(device)
        except NetworkCommandError:
            pass
        return NetworkInfo(ssid, ipv4, signal)

    def ping(self, target: str) -> PingResult:
        clean_target = target.strip()
        if not self._valid_ping_target(clean_target):
            return PingResult(clean_target or "(empty)", False, message="Invalid host")

        command = ["ping", "-c", "1", "-W", "2", clean_target]
        try:
            result = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=self.ping_timeout,
                check=False,
            )
        except FileNotFoundError:
            return PingResult(clean_target, False, message="ping unavailable")
        except subprocess.TimeoutExpired:
            return PingResult(clean_target, False, message="Timed out")
        except OSError:
            return PingResult(clean_target, False, message="Ping error")

        output = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode != 0:
            return PingResult(clean_target, False, message="Unreachable")
        match = PING_TIME_PATTERN.search(output)
        latency = float(match.group(1)) if match else None
        return PingResult(clean_target, True, latency_ms=latency)

    def _connected_wifi_device(self) -> Optional[str]:
        output = self._run_nmcli(
            ["-t", "-f", "DEVICE,TYPE,STATE", "device", "status"]
        )
        for line in output.splitlines():
            fields = self._split_escaped(line)
            if len(fields) >= 3 and fields[1] == "wifi" and fields[2] == "connected":
                return fields[0]
        return None

    def _read_active_wifi(self, device: str):
        output = self._run_nmcli(
            [
                "-t",
                "-f",
                "ACTIVE,SSID,SIGNAL",
                "device",
                "wifi",
                "list",
                "ifname",
                device,
            ]
        )
        for line in output.splitlines():
            fields = self._split_escaped(line)
            if len(fields) < 3 or fields[0] != "yes":
                continue
            try:
                signal = max(0, min(100, int(fields[2])))
            except ValueError:
                signal = None
            return fields[1] or None, signal
        return None, None

    def _read_ipv4(self, device: str) -> Optional[str]:
        output = self._run_nmcli(
            ["-g", "IP4.ADDRESS", "device", "show", device]
        )
        for line in output.splitlines():
            value = line.strip()
            if not value:
                continue
            try:
                return str(ipaddress.ip_interface(value).ip)
            except ValueError:
                continue
        return None

    def _run_nmcli(self, arguments: List[str]) -> str:
        environment = os.environ.copy()
        environment["LC_ALL"] = "C"
        try:
            result = self._runner(
                ["nmcli"] + arguments,
                capture_output=True,
                text=True,
                timeout=self.command_timeout,
                check=False,
                env=environment,
            )
        except FileNotFoundError as exc:
            raise NetworkCommandError("nmcli unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise NetworkCommandError("nmcli timed out") from exc
        except OSError as exc:
            raise NetworkCommandError("Network query failed") from exc
        if result.returncode != 0:
            raise NetworkCommandError("nmcli query failed")
        return result.stdout or ""

    @staticmethod
    def _split_escaped(value: str) -> List[str]:
        fields = []
        current = []
        escaped = False
        for character in value:
            if escaped:
                current.append(character)
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == ":":
                fields.append("".join(current))
                current = []
            else:
                current.append(character)
        if escaped:
            current.append("\\")
        fields.append("".join(current))
        return fields

    @staticmethod
    def _valid_ping_target(target: str) -> bool:
        if not target or len(target) > 253 or target.startswith("-"):
            return False
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            pass
        hostname = target[:-1] if target.endswith(".") else target
        labels = hostname.split(".")
        return all(
            0 < len(label) <= 63 and HOST_LABEL_PATTERN.fullmatch(label)
            for label in labels
        )
