from __future__ import annotations

from collections.abc import Sequence
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from zorix_action_api import ActionContext, ActionExecutor
from zorix_action_model import ActionExecutionStatus, ActionRequest
from zorix_core_model import Resource
from zorix_linux_adapter import LinuxAdapter
from zorix_linux_adapter.action_execution import (
    InvalidLinuxActionPlanError,
    LinuxActionOutputError,
    STATIC_SYSTEMD_ACTION_SCRIPT,
    parse_systemd_action_output,
)


class RecordingRunner:
    def __init__(self, output: str | None = None, error: Exception | None = None) -> None:
        self.output = output if output is not None else _output()
        self.error = error
        self.calls: list[tuple[str, tuple[str, ...], str | None]] = []

    def run(
        self,
        target: str,
        arguments: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> str:
        self.calls.append((target, tuple(arguments), input_text))
        if self.error is not None:
            raise self.error
        return self.output


class LinuxActionExecutionTest(unittest.TestCase):
    def test_linux_adapter_is_action_executor(self) -> None:
        self.assertIsInstance(LinuxAdapter("tandem"), ActionExecutor)

    def test_success_calls_runner_once_with_fixed_shape(self) -> None:
        runner = RecordingRunner(
            _output(
                action="restart",
                unit="zorix-action-smoke.service",
                before_active_state="active",
                before_sub_state="running",
                after_active_state="active",
                after_sub_state="running",
            )
        )
        adapter = LinuxAdapter("tandem", runner)
        resource = _service(unit="zorix-action-smoke.service")
        context = ActionContext([resource])
        plan = adapter.plan_action(context, ActionRequest("service.restart", resource.id))

        result = adapter.execute_action(context, plan)

        self.assertIs(result.status, ActionExecutionStatus.SUCCESS)
        self.assertTrue(result.verified)
        self.assertFalse(result.changed)
        self.assertEqual(result.previous_state, "active")
        self.assertEqual(result.current_state, "active")
        self.assertEqual(
            runner.calls,
            [
                (
                    "tandem",
                    ("sh", "-s", "--", "restart", "zorix-action-smoke.service"),
                    STATIC_SYSTEMD_ACTION_SCRIPT,
                )
            ],
        )

    def test_failed_when_systemd_exit_code_is_nonzero(self) -> None:
        runner = RecordingRunner(_output(action_exit_code="1", after_active_state="failed"))
        adapter = LinuxAdapter("tandem", runner)
        resource = _service()
        context = ActionContext([resource])
        plan = adapter.plan_action(context, ActionRequest("service.start", resource.id))

        result = adapter.execute_action(context, plan)

        self.assertIs(result.status, ActionExecutionStatus.FAILED)
        self.assertFalse(result.verified)
        self.assertIn("exit code 1", result.message)

    def test_mutation_systemctl_output_is_suppressed_and_nonzero_result_is_failed(self) -> None:
        script_output = _run_static_script_with_noisy_failing_systemctl()
        parsed = parse_systemd_action_output(
            script_output,
            expected_action="restart",
            expected_unit="tandem.service",
        )
        runner = RecordingRunner(script_output)
        adapter = LinuxAdapter("tandem", runner)
        resource = _service()
        context = ActionContext([resource])
        plan = adapter.plan_action(context, ActionRequest("service.restart", resource.id))

        result = adapter.execute_action(context, plan)

        self.assertEqual(parsed.action_exit_code, 7)
        self.assertIs(result.status, ActionExecutionStatus.FAILED)
        self.assertFalse(result.verified)
        self.assertEqual(result.metadata["action_exit_code"], "7")
        self.assertEqual(len(runner.calls), 1)

    def test_static_script_suppresses_mutation_stdout_and_stderr(self) -> None:
        self.assertIn('>/dev/null 2>&1', STATIC_SYSTEMD_ACTION_SCRIPT)

    def test_invalid_plan_does_not_call_runner(self) -> None:
        runner = RecordingRunner()
        adapter = LinuxAdapter("tandem", runner)
        resource = _service()
        context = ActionContext([resource])
        plan = adapter.plan_action(context, ActionRequest("service.restart", resource.id))
        bad_plan = type(plan)(
            plan.source,
            "other.Provider",
            plan.request,
            plan.resource_name,
            plan.operation,
            plan.risk,
            plan.requires_confirmation,
            plan.summary,
            plan.steps,
            plan.metadata,
        )

        with self.assertRaises(InvalidLinuxActionPlanError):
            adapter.execute_action(context, bad_plan)

        self.assertEqual(runner.calls, [])

    def test_invalid_resource_unit_does_not_call_runner(self) -> None:
        runner = RecordingRunner()
        adapter = LinuxAdapter("tandem", runner)
        resource = _service()
        context = ActionContext([resource])
        plan = adapter.plan_action(context, ActionRequest("service.restart", resource.id))
        bad_resource = _service(
            unit="tandem;id.service",
            resource_id="linux:service:tandem:tandem;id.service",
        )

        with self.assertRaises(InvalidLinuxActionPlanError):
            adapter.execute_action(ActionContext([bad_resource]), plan)

        self.assertEqual(runner.calls, [])

    def test_output_parser_rejects_malformed_output(self) -> None:
        malformed_cases = (
            "",
            "__ZORIX_SYSTEMD_ACTION_V1_BEGIN__\naction=restart\n",
            "__ZORIX_SYSTEMD_ACTION_V1_BEGIN__\naction=restart\naction=restart\n",
            "__ZORIX_SYSTEMD_ACTION_V1_BEGIN__\nunknown=value\n__ZORIX_SYSTEMD_ACTION_V1_END__\n",
            "text\n" + _output(action="restart"),
            _output(action="stop"),
            _output(unit="other.service"),
            _output(action_exit_code="bad"),
            _output(after_active_state="bad state"),
        )

        for output in malformed_cases:
            with self.subTest(output=output):
                with self.assertRaises(LinuxActionOutputError):
                    parse_systemd_action_output(
                        output,
                        expected_action="restart",
                        expected_unit="tandem.service",
                    )

    def test_output_parser_accepts_valid_output(self) -> None:
        parsed = parse_systemd_action_output(
            _output(action="restart"),
            expected_action="restart",
            expected_unit="tandem.service",
        )

        self.assertEqual(parsed.action, "restart")
        self.assertEqual(parsed.unit, "tandem.service")
        self.assertEqual(parsed.action_exit_code, 0)


def _service(
    *,
    unit: str = "tandem.service",
    resource_id: str | None = None,
) -> Resource:
    resource_id = resource_id if resource_id is not None else f"linux:service:tandem:{unit}"
    return Resource(
        resource_id,
        "service",
        unit,
        "active",
        metadata={
            "host_id": "linux:host:tandem",
            "unit": unit,
            "active_state": "active",
            "sub_state": "running",
        },
    )


def _output(
    *,
    action: str = "start",
    unit: str = "tandem.service",
    before_active_state: str = "inactive",
    before_sub_state: str = "dead",
    action_exit_code: str = "0",
    after_active_state: str = "active",
    after_sub_state: str = "running",
) -> str:
    return (
        "__ZORIX_SYSTEMD_ACTION_V1_BEGIN__\n"
        f"action={action}\n"
        f"unit={unit}\n"
        f"before_active_state={before_active_state}\n"
        f"before_sub_state={before_sub_state}\n"
        f"action_exit_code={action_exit_code}\n"
        f"after_active_state={after_active_state}\n"
        f"after_sub_state={after_sub_state}\n"
        "__ZORIX_SYSTEMD_ACTION_V1_END__\n"
    )


def _run_static_script_with_noisy_failing_systemctl() -> str:
    with tempfile.TemporaryDirectory() as directory:
        fake_systemctl = Path(directory) / "systemctl"
        fake_systemctl.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    'if [ "$1" = "show" ]; then',
                    '    case "$3" in',
                    '        "--property=ActiveState") printf "%s\\n" "inactive" ;;',
                    '        "--property=SubState") printf "%s\\n" "dead" ;;',
                    "        *) exit 2 ;;",
                    "    esac",
                    "    exit 0",
                    "fi",
                    'printf "%s\\n" "noisy mutation stdout"',
                    'printf "%s\\n" "noisy mutation stderr" >&2',
                    "exit 7",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        fake_systemctl.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{directory}{os.pathsep}{env.get('PATH', '')}"

        completed = subprocess.run(
            ("sh", "-s", "--", "restart", "tandem.service"),
            input=STATIC_SYSTEMD_ACTION_SCRIPT,
            capture_output=True,
            text=True,
            shell=False,
            env=env,
            check=False,
        )

    if completed.returncode != 0:
        raise AssertionError(f"static script failed with exit code {completed.returncode}")
    if completed.stderr:
        raise AssertionError(f"static script leaked stderr: {completed.stderr}")
    if "noisy mutation stdout" in completed.stdout:
        raise AssertionError("static script leaked mutation stdout")
    if "noisy mutation stderr" in completed.stdout:
        raise AssertionError("static script leaked mutation stderr")

    return completed.stdout


if __name__ == "__main__":
    unittest.main()
