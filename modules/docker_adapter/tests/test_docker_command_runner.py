from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import subprocess
import unittest
from unittest.mock import patch

from zorix_docker_adapter.command import SubprocessDockerCommandRunner
from zorix_docker_adapter.errors import (
    DockerCommandError,
    DockerCommandTimeoutError,
    DockerExecutableNotFoundError,
)


class SubprocessDockerCommandRunnerTest(unittest.TestCase):
    def test_default_executable_is_docker(self) -> None:
        runner = SubprocessDockerCommandRunner()

        self.assertEqual(runner.executable, "docker")

    def test_custom_executable_is_used(self) -> None:
        runner = SubprocessDockerCommandRunner(executable="podman")
        completed = subprocess.CompletedProcess(
            args=["podman"],
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

        with patch("zorix_docker_adapter.command.subprocess.run", return_value=completed) as run:
            runner.run(("container", "ls"))

        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["podman", "container", "ls"])

    def test_arguments_and_subprocess_options_are_passed(self) -> None:
        runner = SubprocessDockerCommandRunner(timeout_seconds=12.5)
        completed = subprocess.CompletedProcess(
            args=["docker"],
            returncode=0,
            stdout="",
            stderr="",
        )

        with patch("zorix_docker_adapter.command.subprocess.run", return_value=completed) as run:
            runner.run(("container", "inspect", "abc"))

        run.assert_called_once_with(
            ["docker", "container", "inspect", "abc"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=12.5,
        )

    def test_stdout_is_returned_without_printing(self) -> None:
        runner = SubprocessDockerCommandRunner()
        completed = subprocess.CompletedProcess(
            args=["docker"],
            returncode=0,
            stdout="container-id\n",
            stderr="ignored\n",
        )
        stdout = StringIO()
        stderr = StringIO()

        with patch("zorix_docker_adapter.command.subprocess.run", return_value=completed):
            with redirect_stdout(stdout):
                with redirect_stderr(stderr):
                    result = runner.run(("container", "ls"))

        self.assertEqual(result, "container-id\n")
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_non_zero_return_code_raises_command_error(self) -> None:
        runner = SubprocessDockerCommandRunner()
        completed = subprocess.CompletedProcess(
            args=["docker"],
            returncode=17,
            stdout="not shown\n",
            stderr=" daemon unavailable \n",
        )

        with patch("zorix_docker_adapter.command.subprocess.run", return_value=completed):
            with self.assertRaises(DockerCommandError) as context:
                runner.run(("container", "ls"))

        error = context.exception
        self.assertEqual(error.command, ("docker", "container", "ls"))
        self.assertEqual(error.return_code, 17)
        self.assertEqual(error.stderr, " daemon unavailable \n")
        self.assertEqual(
            str(error),
            "Docker command failed with exit code 17: daemon unavailable",
        )

    def test_empty_stderr_command_error_message_has_no_colon(self) -> None:
        runner = SubprocessDockerCommandRunner()
        completed = subprocess.CompletedProcess(
            args=["docker"],
            returncode=1,
            stdout="",
            stderr="   ",
        )

        with patch("zorix_docker_adapter.command.subprocess.run", return_value=completed):
            with self.assertRaises(DockerCommandError) as context:
                runner.run(("container", "inspect", "abc"))

        self.assertEqual(str(context.exception), "Docker command failed with exit code 1")

    def test_file_not_found_raises_typed_error(self) -> None:
        runner = SubprocessDockerCommandRunner(executable="missing-docker")

        with patch(
            "zorix_docker_adapter.command.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            with self.assertRaises(DockerExecutableNotFoundError) as context:
                runner.run(("container", "ls"))

        self.assertEqual(
            str(context.exception),
            "Docker CLI executable was not found: missing-docker",
        )

    def test_timeout_raises_typed_error(self) -> None:
        runner = SubprocessDockerCommandRunner(timeout_seconds=2.0)

        with patch(
            "zorix_docker_adapter.command.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["docker"], timeout=2.0),
        ):
            with self.assertRaises(DockerCommandTimeoutError) as context:
                runner.run(("container", "ls"))

        self.assertIn("docker container ls", str(context.exception))
        self.assertIn("2.0", str(context.exception))

    def test_non_positive_timeout_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SubprocessDockerCommandRunner(timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
