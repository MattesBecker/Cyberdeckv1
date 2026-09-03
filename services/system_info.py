import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple


@dataclass(frozen=True)
class SystemInfo:
    hostname: str
    uptime_seconds: Optional[float]
    cpu_percent: Optional[float]
    memory_used_mb: Optional[int]
    memory_total_mb: Optional[int]
    disk_free_bytes: Optional[int]


class SystemInfoService:
    """Read a small system snapshot without background monitoring."""

    def __init__(
        self,
        proc_root: Path = Path("/proc"),
        disk_path: Path = Path("/"),
        cpu_sample_interval: float = 0.1,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.proc_root = Path(proc_root)
        self.disk_path = Path(disk_path)
        self.cpu_sample_interval = cpu_sample_interval
        self._sleeper = sleeper

    def read(self) -> SystemInfo:
        memory_used, memory_total = self._read_memory_mb()
        return SystemInfo(
            hostname=self._read_hostname(),
            uptime_seconds=self._read_uptime(),
            cpu_percent=self._read_cpu_percent(),
            memory_used_mb=memory_used,
            memory_total_mb=memory_total,
            disk_free_bytes=self._read_disk_free(),
        )

    @staticmethod
    def _read_hostname() -> str:
        try:
            return socket.gethostname() or "unknown"
        except OSError:
            return "unknown"

    def _read_uptime(self) -> Optional[float]:
        try:
            value = (self.proc_root / "uptime").read_text(
                encoding="utf-8"
            ).split()[0]
            return max(0.0, float(value))
        except (OSError, UnicodeError, ValueError, IndexError):
            return None

    def _read_cpu_percent(self) -> Optional[float]:
        first = self._read_cpu_times()
        if first is None:
            return None
        self._sleeper(self.cpu_sample_interval)
        second = self._read_cpu_times()
        if second is None:
            return None

        total_delta = second[0] - first[0]
        idle_delta = second[1] - first[1]
        if total_delta <= 0:
            return None
        percent = 100.0 * (total_delta - idle_delta) / total_delta
        return max(0.0, min(100.0, percent))

    def _read_cpu_times(self) -> Optional[Tuple[int, int]]:
        try:
            first_line = (self.proc_root / "stat").read_text(
                encoding="utf-8"
            ).splitlines()[0]
            fields = first_line.split()
            if not fields or fields[0] != "cpu":
                return None
            values = [int(value) for value in fields[1:9]]
            if len(values) < 4:
                return None
            total = sum(values)
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            return total, idle
        except (OSError, UnicodeError, ValueError, IndexError):
            return None

    def _read_memory_mb(self) -> Tuple[Optional[int], Optional[int]]:
        try:
            lines = (self.proc_root / "meminfo").read_text(
                encoding="utf-8"
            ).splitlines()
        except (OSError, UnicodeError):
            return None, None

        values = {}
        for line in lines:
            if ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            parts = raw_value.strip().split()
            if not parts:
                continue
            try:
                values[key] = int(parts[0])
            except ValueError:
                continue

        total_kb = values.get("MemTotal")
        available_kb = values.get("MemAvailable", values.get("MemFree"))
        if total_kb is None or available_kb is None:
            return None, None
        used_kb = max(0, total_kb - available_kb)
        return int(round(used_kb / 1024.0)), int(round(total_kb / 1024.0))

    def _read_disk_free(self) -> Optional[int]:
        try:
            return shutil.disk_usage(str(self.disk_path)).free
        except OSError:
            return None


class SystemActionError(RuntimeError):
    """Raised when a requested reboot or shutdown cannot be started."""


class PowerController:
    """Execute one confirmed system power action without using a shell."""

    COMMANDS = {
        "reboot": ["sudo", "-n", "shutdown", "-r", "now"],
        "shutdown": ["sudo", "-n", "shutdown", "-h", "now"],
    }

    def __init__(
        self,
        runner: Callable = subprocess.run,
        timeout: float = 10.0,
    ) -> None:
        self._runner = runner
        self.timeout = timeout

    def execute(self, action: str) -> None:
        command = self.COMMANDS.get(action)
        if command is None:
            raise SystemActionError("Unknown power action: {0}".format(action))
        try:
            result = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise SystemActionError("sudo or shutdown is not available.") from exc
        except subprocess.TimeoutExpired as exc:
            raise SystemActionError("Power command timed out.") from exc
        except OSError as exc:
            raise SystemActionError(
                "Could not run power command: {0}".format(exc)
            ) from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            if detail:
                detail = detail.splitlines()[0]
            else:
                detail = "exit status {0}".format(result.returncode)
            raise SystemActionError(
                "Power command was rejected: {0}".format(detail)
            )
