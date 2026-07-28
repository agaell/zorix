from __future__ import annotations


class DockerAdapterError(RuntimeError):
    pass


class DockerExecutableNotFoundError(DockerAdapterError):
    def __init__(self, executable: str) -> None:
        self.executable = executable
        super().__init__(f"Docker CLI executable was not found: {executable}")


class DockerCommandError(DockerAdapterError):
    def __init__(self, command: tuple[str, ...], return_code: int, stderr: str) -> None:
        self.command = command
        self.return_code = return_code
        self.stderr = stderr

        display_stderr = stderr.strip()
        if display_stderr:
            message = f"Docker command failed with exit code {return_code}: {display_stderr}"
        else:
            message = f"Docker command failed with exit code {return_code}"

        super().__init__(message)


class DockerCommandTimeoutError(DockerAdapterError):
    def __init__(self, command: tuple[str, ...], timeout_seconds: float) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        command_text = " ".join(command)
        super().__init__(
            f"Docker command timed out after {timeout_seconds} seconds: {command_text}"
        )


class DockerOutputError(DockerAdapterError):
    pass
