from __future__ import annotations

from collections.abc import Sequence
import subprocess
from typing import Protocol

from .errors import (
    DockerCommandError,
    DockerCommandTimeoutError,
    DockerExecutableNotFoundError,
)


class DockerCommandRunner(Protocol):
    def run(self, arguments: Sequence[str]) -> str:
        ...


class SubprocessDockerCommandRunner:
    def __init__(self, executable: str = "docker", timeout_seconds: float = 30.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: Sequence[str]) -> str:
        command = (self.executable, *arguments)

        try:
            completed = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                shell=False,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise DockerExecutableNotFoundError(self.executable) from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerCommandTimeoutError(command, self.timeout_seconds) from exc

        if completed.returncode != 0:
            raise DockerCommandError(command, completed.returncode, completed.stderr)

        return completed.stdout
