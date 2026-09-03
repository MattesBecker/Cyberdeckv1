import logging
import os
import tempfile
from pathlib import Path
from typing import List


logger = logging.getLogger(__name__)


class TerminalHistoryError(RuntimeError):
    """Raised when terminal history cannot be accessed safely."""


class TerminalHistoryStore:
    """Persist a bounded command history as private UTF-8 text."""

    def __init__(self, history_file: Path, limit: int = 20) -> None:
        if limit <= 0:
            raise ValueError("History limit must be greater than zero.")
        self.history_file = Path(history_file)
        self.limit = limit

    def ensure_file(self) -> None:
        if self.history_file.is_symlink():
            raise TerminalHistoryError(
                "Terminal history must not be a symbolic link."
            )
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise TerminalHistoryError(
                "Could not create terminal history directory: {0}".format(exc)
            ) from exc
        if self.history_file.exists():
            if not self.history_file.is_file():
                raise TerminalHistoryError(
                    "Terminal history path is not a regular file."
                )
            return
        self._atomic_write([])

    def load(self) -> List[str]:
        self.ensure_file()
        try:
            raw_data = self.history_file.read_bytes()
            text = raw_data.decode("utf-8")
        except UnicodeError as exc:
            raise TerminalHistoryError(
                "Terminal history is not valid UTF-8."
            ) from exc
        except OSError as exc:
            raise TerminalHistoryError(
                "Could not read terminal history: {0}".format(exc)
            ) from exc

        commands = [line for line in text.splitlines() if line.strip()]
        return commands[-self.limit :]

    def add(self, command: str) -> List[str]:
        clean_command = command.replace("\r", " ").replace("\n", " ").strip()
        commands = self.load()
        if not clean_command:
            return commands
        commands.append(clean_command)
        commands = commands[-self.limit :]
        self._atomic_write(commands)
        return commands

    def _atomic_write(self, commands: List[str]) -> None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=".terminal_history.",
                suffix=".tmp",
                dir=str(self.history_file.parent),
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                for command in commands:
                    temporary_file.write(command + "\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(str(temporary_path), str(self.history_file))
            temporary_path = None
        except OSError as exc:
            raise TerminalHistoryError(
                "Could not save terminal history: {0}".format(exc)
            ) from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    logger.warning(
                        "Could not remove temporary history file: %s",
                        temporary_path.name,
                    )
