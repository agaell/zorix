from __future__ import annotations

from collections.abc import Sequence
import subprocess
from typing import Protocol

from .errors import (
    SshCommandError,
    SshCommandTimeoutError,
    SshExecutableNotFoundError,
)


class SshCommandRunner(Protocol):
    def run(
        self,
        target: str,
        arguments: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> str:
        ...


class SubprocessSshCommandRunner:
    def __init__(
        self,
        executable: str = "ssh",
        connect_timeout_seconds: int = 10,
        command_timeout_seconds: float = 30.0,
    ) -> None:
        if (
            isinstance(connect_timeout_seconds, bool)
            or not isinstance(connect_timeout_seconds, int)
            or connect_timeout_seconds <= 0
        ):
            raise ValueError("connect_timeout_seconds must be a positive integer")

        if (
            isinstance(command_timeout_seconds, bool)
            or not isinstance(command_timeout_seconds, (int, float))
            or command_timeout_seconds <= 0
        ):
            raise ValueError("command_timeout_seconds must be positive")

        self.executable = executable
        self.connect_timeout_seconds = connect_timeout_seconds
        self.command_timeout_seconds = float(command_timeout_seconds)

    def run(
        self,
        target: str,
        arguments: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> str:
        remote_arguments = tuple(arguments)
        command = (
            self.executable,
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self.connect_timeout_seconds}",
            target,
            *remote_arguments,
        )

        try:
            completed = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                shell=False,
                timeout=self.command_timeout_seconds,
                input=input_text,
            )
        except FileNotFoundError as exc:
            raise SshExecutableNotFoundError(self.executable) from exc
        except subprocess.TimeoutExpired as exc:
            raise SshCommandTimeoutError(
                target,
                remote_arguments,
                self.command_timeout_seconds,
            ) from exc

        if completed.returncode != 0:
            raise SshCommandError(
                target,
                remote_arguments,
                completed.returncode,
                completed.stderr,
            )

        return completed.stdout
