from __future__ import annotations


class LinuxAdapterError(RuntimeError):
    pass


class LinuxConfigurationError(LinuxAdapterError):
    pass


class SshExecutableNotFoundError(LinuxAdapterError):
    def __init__(self, executable: str) -> None:
        self.executable = executable
        super().__init__(f"SSH executable was not found: {executable}")


class SshCommandError(LinuxAdapterError):
    def __init__(
        self,
        target: str,
        command: tuple[str, ...],
        return_code: int,
        stderr: str,
    ) -> None:
        self.target = target
        self.command = command
        self.return_code = return_code
        self.stderr = stderr

        display_stderr = stderr.strip()
        if display_stderr:
            message = (
                f"SSH command failed for {target} with exit code "
                f"{return_code}: {display_stderr}"
            )
        else:
            message = f"SSH command failed for {target} with exit code {return_code}"

        super().__init__(message)


class SshCommandTimeoutError(LinuxAdapterError):
    def __init__(
        self,
        target: str,
        command: tuple[str, ...],
        timeout_seconds: float,
    ) -> None:
        self.target = target
        self.command = command
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"SSH command timed out for {target} after {timeout_seconds} seconds"
        )


class LinuxOutputError(LinuxAdapterError):
    pass
