import re
import shlex
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Union


ANSI_ESCAPE_PATTERN = re.compile(
    r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
)


@dataclass(frozen=True)
class CommandResult:
    command: str
    arguments: Tuple[str, ...]
    stdout: str
    stderr: str
    return_code: Optional[int]
    error: str = ""
    timed_out: bool = False


class TerminalService:
    """Run one non-interactive command without invoking a shell."""

    def __init__(
        self,
        timeout: float = 10.0,
        runner: Callable = subprocess.run,
    ) -> None:
        if timeout <= 0:
            raise ValueError("Command timeout must be greater than zero.")
        self.timeout = timeout
        self._runner = runner

    def execute(self, command: str) -> CommandResult:
        clean_command = command.strip()
        if not clean_command:
            return CommandResult(
                command="",
                arguments=(),
                stdout="",
                stderr="",
                return_code=None,
                error="Command must not be empty.",
            )

        try:
            arguments = tuple(shlex.split(clean_command, posix=True))
        except ValueError as exc:
            return CommandResult(
                command=clean_command,
                arguments=(),
                stdout="",
                stderr="",
                return_code=None,
                error="Invalid command line: {0}".format(exc),
            )
        if not arguments:
            return CommandResult(
                command=clean_command,
                arguments=(),
                stdout="",
                stderr="",
                return_code=None,
                error="Command must not be empty.",
            )

        try:
            completed = self._runner(
                list(arguments),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError:
            return self._error_result(
                clean_command,
                arguments,
                "Command not found: {0}".format(arguments[0]),
            )
        except PermissionError:
            return self._error_result(
                clean_command,
                arguments,
                "Permission denied: {0}".format(arguments[0]),
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=clean_command,
                arguments=arguments,
                stdout=self._decode_output(exc.stdout),
                stderr=self._decode_output(exc.stderr),
                return_code=None,
                error="Command timed out after {0:g} seconds.".format(
                    self.timeout
                ),
                timed_out=True,
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return self._error_result(
                clean_command,
                arguments,
                "Could not execute command: {0}".format(exc),
            )

        return CommandResult(
            command=clean_command,
            arguments=arguments,
            stdout=self._decode_output(completed.stdout),
            stderr=self._decode_output(completed.stderr),
            return_code=completed.returncode,
        )

    @staticmethod
    def _decode_output(value: Union[bytes, str, None]) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            text = value.decode("utf-8", errors="replace")
        else:
            text = value
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = ANSI_ESCAPE_PATTERN.sub("", text)
        return "".join(
            character
            if character in ("\n", "\t") or ord(character) >= 32
            else "?"
            for character in text
        )

    @staticmethod
    def _error_result(
        command: str, arguments: Tuple[str, ...], message: str
    ) -> CommandResult:
        return CommandResult(
            command=command,
            arguments=arguments,
            stdout="",
            stderr="",
            return_code=None,
            error=message,
        )
