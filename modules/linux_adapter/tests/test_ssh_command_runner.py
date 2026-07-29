from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import subprocess
import unittest
from unittest.mock import patch

from zorix_linux_adapter.command import SubprocessSshCommandRunner
from zorix_linux_adapter.errors import (
    SshCommandError,
    SshCommandTimeoutError,
    SshExecutableNotFoundError,
)


class SubprocessSshCommandRunnerTest(unittest.TestCase):
    def test_default_executable_is_ssh(self) -> None:
        runner = SubprocessSshCommandRunner()

        self.assertEqual(runner.executable, "ssh")

    def test_custom_executable_is_used(self) -> None:
        runner = SubprocessSshCommandRunner(executable="custom-ssh")
        completed = subprocess.CompletedProcess(
            args=["custom-ssh"],
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

        with patch("zorix_linux_adapter.command.subprocess.run", return_value=completed) as run:
            runner.run("target", ("hostname",))

        self.assertEqual(run.call_args.args[0][0], "custom-ssh")

    def test_arguments_and_subprocess_options_are_passed(self) -> None:
        runner = SubprocessSshCommandRunner(
            connect_timeout_seconds=7,
            command_timeout_seconds=12.5,
        )
        completed = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=0,
            stdout="",
            stderr="",
        )

        with patch("zorix_linux_adapter.command.subprocess.run", return_value=completed) as run:
            runner.run("tandem", ("env", "LC_ALL=C", "hostname"))

        run.assert_called_once_with(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=7",
                "tandem",
                "env",
                "LC_ALL=C",
                "hostname",
            ],
            capture_output=True,
            text=True,
            shell=False,
            timeout=12.5,
            input=None,
        )

    def test_input_text_is_passed_to_subprocess(self) -> None:
        runner = SubprocessSshCommandRunner()
        completed = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

        with patch("zorix_linux_adapter.command.subprocess.run", return_value=completed) as run:
            result = runner.run("target", ("sh", "-s"), input_text="script body")

        self.assertEqual(result, "ok\n")
        self.assertEqual(run.call_args.kwargs["input"], "script body")

    def test_stdout_is_returned_without_printing(self) -> None:
        runner = SubprocessSshCommandRunner()
        completed = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=0,
            stdout="remote stdout\n",
            stderr="remote stderr\n",
        )
        stdout = StringIO()
        stderr = StringIO()

        with patch("zorix_linux_adapter.command.subprocess.run", return_value=completed):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = runner.run("target", ("hostname",))

        self.assertEqual(result, "remote stdout\n")
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_non_zero_return_code_raises_command_error(self) -> None:
        runner = SubprocessSshCommandRunner()
        completed = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=255,
            stdout="not shown\n",
            stderr=" permission denied \n",
        )

        with patch("zorix_linux_adapter.command.subprocess.run", return_value=completed):
            with self.assertRaises(SshCommandError) as context:
                runner.run("target", ("hostname",))

        error = context.exception
        self.assertEqual(error.target, "target")
        self.assertEqual(error.command, ("hostname",))
        self.assertEqual(error.return_code, 255)
        self.assertEqual(error.stderr, " permission denied \n")
        self.assertEqual(
            str(error),
            "SSH command failed for target with exit code 255: permission denied",
        )

    def test_non_zero_snapshot_command_error_does_not_include_script(self) -> None:
        runner = SubprocessSshCommandRunner()
        completed = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=1,
            stdout="",
            stderr="failed\n",
        )

        with patch("zorix_linux_adapter.command.subprocess.run", return_value=completed):
            with self.assertRaises(SshCommandError) as context:
                runner.run("target", ("sh", "-s"), input_text="secret script")

        self.assertEqual(context.exception.command, ("sh", "-s"))
        self.assertNotIn("secret script", str(context.exception))

    def test_empty_stderr_command_error_message_has_no_colon(self) -> None:
        runner = SubprocessSshCommandRunner()
        completed = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=1,
            stdout="",
            stderr="   ",
        )

        with patch("zorix_linux_adapter.command.subprocess.run", return_value=completed):
            with self.assertRaises(SshCommandError) as context:
                runner.run("target", ("hostname",))

        self.assertEqual(str(context.exception), "SSH command failed for target with exit code 1")

    def test_file_not_found_raises_typed_error(self) -> None:
        runner = SubprocessSshCommandRunner(executable="missing-ssh")

        with patch(
            "zorix_linux_adapter.command.subprocess.run",
            side_effect=FileNotFoundError(),
        ):
            with self.assertRaises(SshExecutableNotFoundError) as context:
                runner.run("target", ("hostname",))

        self.assertEqual(str(context.exception), "SSH executable was not found: missing-ssh")

    def test_timeout_raises_typed_error(self) -> None:
        runner = SubprocessSshCommandRunner(command_timeout_seconds=2.0)

        with patch(
            "zorix_linux_adapter.command.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["ssh"], timeout=2.0),
        ):
            with self.assertRaises(SshCommandTimeoutError) as context:
                runner.run("target", ("hostname",))

        self.assertEqual(context.exception.target, "target")
        self.assertEqual(context.exception.command, ("hostname",))
        self.assertIn("target", str(context.exception))
        self.assertIn("2.0", str(context.exception))

    def test_invalid_connect_timeout_is_rejected(self) -> None:
        for value in (0, -1, 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SubprocessSshCommandRunner(connect_timeout_seconds=value)  # type: ignore[arg-type]

    def test_invalid_command_timeout_is_rejected(self) -> None:
        for value in (0, -1, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SubprocessSshCommandRunner(command_timeout_seconds=value)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
