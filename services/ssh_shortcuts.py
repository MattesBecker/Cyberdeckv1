import ipaddress
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, List, Optional

from json_store import JSONStoreError, load_json, save_json


HOST_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
USER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,31}$")


class SSHShortcutError(RuntimeError):
    pass


@dataclass(frozen=True)
class SSHShortcut:
    name: str
    host: str
    user: str
    port: int
    command: str


@dataclass(frozen=True)
class SSHResult:
    success: bool
    output: str


class SSHShortcutStore:
    def __init__(self, path: Path, limit: int = 100) -> None:
        self.path = Path(path)
        self.limit = max(1, int(limit))

    def list(self) -> List[SSHShortcut]:
        raw = load_json(self.path, [])
        if not isinstance(raw, list):
            return []
        result = []
        for value in raw[: self.limit]:
            item = self._parse(value)
            if item is not None:
                result.append(item)
        return result

    def add(self, shortcut: SSHShortcut) -> None:
        self.validate(shortcut)
        items = self.list()
        if len(items) >= self.limit:
            raise SSHShortcutError("Shortcut limit reached")
        self._save(items + [shortcut])

    def replace(self, index: int, shortcut: SSHShortcut) -> None:
        self.validate(shortcut)
        items = self.list()
        if index < 0 or index >= len(items):
            raise SSHShortcutError("Shortcut no longer exists")
        items[index] = shortcut
        self._save(items)

    def delete(self, index: int) -> None:
        items = self.list()
        if index < 0 or index >= len(items):
            raise SSHShortcutError("Shortcut no longer exists")
        del items[index]
        self._save(items)

    @staticmethod
    def validate(shortcut: SSHShortcut) -> None:
        if not isinstance(shortcut, SSHShortcut):
            raise SSHShortcutError("Invalid shortcut")
        name = " ".join(shortcut.name.splitlines()).strip()
        command = " ".join(shortcut.command.splitlines()).strip()
        if not name or len(name) > 60:
            raise SSHShortcutError("Invalid name")
        if not _valid_host(shortcut.host):
            raise SSHShortcutError("Invalid host")
        if USER_PATTERN.fullmatch(shortcut.user) is None:
            raise SSHShortcutError("Invalid user")
        if not isinstance(shortcut.port, int) or isinstance(shortcut.port, bool) or not 1 <= shortcut.port <= 65535:
            raise SSHShortcutError("Invalid port")
        if not command or len(command) > 500 or any(character in shortcut.command for character in "\x00\r\n"):
            raise SSHShortcutError("Invalid command")

    def _save(self, items: List[SSHShortcut]) -> None:
        try:
            save_json(self.path, [asdict(item) for item in items])
        except JSONStoreError as exc:
            raise SSHShortcutError(str(exc)) from exc

    @classmethod
    def _parse(cls, value) -> Optional[SSHShortcut]:
        if not isinstance(value, dict):
            return None
        try:
            shortcut = SSHShortcut(
                name=value["name"],
                host=value["host"],
                user=value["user"],
                port=value["port"],
                command=value["command"],
            )
            cls.validate(shortcut)
            return shortcut
        except (KeyError, TypeError, SSHShortcutError):
            return None


class SSHShortcutService:
    def __init__(
        self,
        runner: Callable = subprocess.run,
        timeout: float = 12.0,
        max_output_chars: int = 256 * 1024,
    ) -> None:
        self._runner = runner
        self.timeout = timeout
        self.max_output_chars = max(1024, int(max_output_chars))

    def run(self, shortcut: SSHShortcut) -> SSHResult:
        SSHShortcutStore.validate(shortcut)
        host = "[{0}]".format(shortcut.host) if ":" in shortcut.host else shortcut.host
        command = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            "-o", "PasswordAuthentication=no",
            "-p", str(shortcut.port),
            "{0}@{1}".format(shortcut.user, host),
            shortcut.command,
        ]
        try:
            result = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                shell=False,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            return SSHResult(False, "ssh client unavailable")
        except subprocess.TimeoutExpired:
            return SSHResult(False, "SSH timed out")
        except OSError:
            return SSHResult(False, "Could not start ssh")
        output = "\n".join(
            part.strip() for part in (result.stdout or "", result.stderr or "")
            if part.strip()
        )
        if not output:
            output = "Command completed" if result.returncode == 0 else "SSH failed"
        elif len(output) > self.max_output_chars:
            output = output[: self.max_output_chars] + "\n[output truncated]"
        return SSHResult(result.returncode == 0, output)


def _valid_host(host: str) -> bool:
    if not isinstance(host, str) or not host or host.startswith("-") or len(host) > 253:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return HOST_PATTERN.fullmatch(host) is not None and ".." not in host
