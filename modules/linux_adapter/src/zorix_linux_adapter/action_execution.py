from __future__ import annotations

from dataclasses import dataclass
import re

from zorix_action_api import ActionContext
from zorix_action_model import (
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionPlan,
)
from zorix_core_model import Resource

from .actions import _OPERATIONS, _service_unit, _valid_service_unit
from .command import SshCommandRunner
from .errors import (
    LinuxAdapterError,
    LinuxOutputError,
    SshCommandError,
    SshCommandTimeoutError,
    SshExecutableNotFoundError,
)


class InvalidLinuxActionPlanError(LinuxAdapterError):
    pass


class LinuxActionOutputError(LinuxOutputError):
    pass


MAX_SYSTEMD_ACTION_OUTPUT_SIZE = 65_536
SYSTEMD_ACTION_BEGIN_MARKER = "__ZORIX_SYSTEMD_ACTION_V1_BEGIN__"
SYSTEMD_ACTION_END_MARKER = "__ZORIX_SYSTEMD_ACTION_V1_END__"
_STATE_PATTERN = re.compile(r"[A-Za-z0-9_.@:-]+\Z")
_ACTION_TOKENS = {
    "service.start": ("linux.systemd.start", "start", "active", "started"),
    "service.stop": ("linux.systemd.stop", "stop", "inactive", "stopped"),
    "service.restart": ("linux.systemd.restart", "restart", "active", "restarted"),
}
_REQUIRED_KEYS = (
    "action",
    "unit",
    "before_active_state",
    "before_sub_state",
    "action_exit_code",
    "after_active_state",
    "after_sub_state",
)

# This script is static production code and does not interpolate target, unit, or command text.
STATIC_SYSTEMD_ACTION_SCRIPT = """\
action="$1"
unit="$2"

case "$action" in
    start|stop|restart) ;;
    *) exit 64 ;;
esac

case "$unit" in
    ""|-*|*/*|*\\\\*|*[\ \	]*|*[\\;\\|\\&\\`\\$\\<\\>\\(\\)]*) exit 65 ;;
esac

case "$unit" in
    *[!ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.@:-]*) exit 65 ;;
esac

case "$unit" in
    *.service) ;;
    *) exit 65 ;;
esac

before_active_state=$(env LC_ALL=C systemctl show "$unit" --property=ActiveState --value 2>/dev/null)
before_sub_state=$(env LC_ALL=C systemctl show "$unit" --property=SubState --value 2>/dev/null)

env LC_ALL=C systemctl "$action" -- "$unit" >/dev/null 2>&1
action_exit_code=$?

after_active_state=$(env LC_ALL=C systemctl show "$unit" --property=ActiveState --value 2>/dev/null)
after_sub_state=$(env LC_ALL=C systemctl show "$unit" --property=SubState --value 2>/dev/null)

printf '%s\\n' '__ZORIX_SYSTEMD_ACTION_V1_BEGIN__'
printf 'action=%s\\n' "$action"
printf 'unit=%s\\n' "$unit"
printf 'before_active_state=%s\\n' "$before_active_state"
printf 'before_sub_state=%s\\n' "$before_sub_state"
printf 'action_exit_code=%s\\n' "$action_exit_code"
printf 'after_active_state=%s\\n' "$after_active_state"
printf 'after_sub_state=%s\\n' "$after_sub_state"
printf '%s\\n' '__ZORIX_SYSTEMD_ACTION_V1_END__'
"""


@dataclass(frozen=True)
class SystemdActionOutput:
    action: str
    unit: str
    before_active_state: str
    before_sub_state: str
    action_exit_code: int
    after_active_state: str
    after_sub_state: str


def execute_linux_action(
    *,
    target: str,
    provider: str,
    runner: SshCommandRunner,
    context: ActionContext,
    plan: ActionPlan,
) -> ActionExecutionResult:
    unit, action_token, expected_state, success_verb = _validate_plan(
        target=target,
        provider=provider,
        context=context,
        plan=plan,
    )

    try:
        output = runner.run(
            target,
            ("sh", "-s", "--", action_token, unit),
            input_text=STATIC_SYSTEMD_ACTION_SCRIPT,
        )
    except (SshExecutableNotFoundError, SshCommandError, SshCommandTimeoutError) as error:
        return ActionExecutionResult(
            status=ActionExecutionStatus.FAILED,
            request=plan.request,
            plan=plan,
            previous_state=None,
            current_state=None,
            changed=False,
            verified=False,
            message=_safe_error_message(error),
            metadata={"unit": unit},
        )

    parsed = parse_systemd_action_output(
        output,
        expected_action=action_token,
        expected_unit=unit,
    )
    changed = (
        parsed.before_active_state != parsed.after_active_state
        or parsed.before_sub_state != parsed.after_sub_state
    )
    verified = parsed.action_exit_code == 0 and parsed.after_active_state == expected_state

    if verified:
        status = ActionExecutionStatus.SUCCESS
        message = f"systemd service {unit} was {success_verb} successfully"
    else:
        status = ActionExecutionStatus.FAILED
        if parsed.action_exit_code != 0:
            message = f"systemd action {action_token} failed with exit code {parsed.action_exit_code}"
        else:
            message = f"systemd service {unit} did not reach expected state {expected_state}"

    return ActionExecutionResult(
        status=status,
        request=plan.request,
        plan=plan,
        previous_state=parsed.before_active_state,
        current_state=parsed.after_active_state,
        changed=changed,
        verified=verified,
        message=message,
        metadata={
            "unit": unit,
            "action_exit_code": str(parsed.action_exit_code),
            "before_sub_state": parsed.before_sub_state,
            "after_sub_state": parsed.after_sub_state,
        },
    )


def parse_systemd_action_output(
    output: str,
    *,
    expected_action: str,
    expected_unit: str,
) -> SystemdActionOutput:
    if not isinstance(output, str):
        raise LinuxActionOutputError("systemd action output must be text")
    if len(output) > MAX_SYSTEMD_ACTION_OUTPUT_SIZE:
        raise LinuxActionOutputError("systemd action output is too large")

    seen_begin = False
    seen_end = False
    values: dict[str, str] = {}

    for raw_line in output.splitlines():
        line = raw_line.rstrip("\r")
        if line == SYSTEMD_ACTION_BEGIN_MARKER:
            if seen_begin or seen_end:
                raise LinuxActionOutputError("duplicate or misplaced begin marker")
            seen_begin = True
            continue
        if line == SYSTEMD_ACTION_END_MARKER:
            if not seen_begin or seen_end:
                raise LinuxActionOutputError("misplaced end marker")
            seen_end = True
            continue
        if line.startswith("__ZORIX_SYSTEMD_ACTION_V1_"):
            raise LinuxActionOutputError("malformed systemd action marker")

        if not seen_begin or seen_end:
            if line.strip():
                raise LinuxActionOutputError("unexpected content outside systemd action markers")
            continue

        if "=" not in line:
            raise LinuxActionOutputError("malformed systemd action output line")
        key, value = line.split("=", 1)
        if key not in _REQUIRED_KEYS:
            raise LinuxActionOutputError(f"unknown systemd action output key: {key}")
        if key in values:
            raise LinuxActionOutputError(f"duplicate systemd action output key: {key}")
        values[key] = value

    if not seen_begin or not seen_end:
        raise LinuxActionOutputError("systemd action output markers are missing")
    for key in _REQUIRED_KEYS:
        if key not in values:
            raise LinuxActionOutputError(f"systemd action output key is missing: {key}")

    if values["action"] != expected_action:
        raise LinuxActionOutputError("systemd action output action does not match plan")
    if values["unit"] != expected_unit:
        raise LinuxActionOutputError("systemd action output unit does not match plan")

    exit_code = _exit_code(values["action_exit_code"])
    before_active_state = _state(values["before_active_state"], "before_active_state")
    before_sub_state = _state(values["before_sub_state"], "before_sub_state")
    after_active_state = _state(values["after_active_state"], "after_active_state")
    after_sub_state = _state(values["after_sub_state"], "after_sub_state")

    return SystemdActionOutput(
        action=values["action"],
        unit=values["unit"],
        before_active_state=before_active_state,
        before_sub_state=before_sub_state,
        action_exit_code=exit_code,
        after_active_state=after_active_state,
        after_sub_state=after_sub_state,
    )


def _validate_plan(
    *,
    target: str,
    provider: str,
    context: ActionContext,
    plan: ActionPlan,
) -> tuple[str, str, str, str]:
    if plan.source != "linux":
        raise InvalidLinuxActionPlanError("plan source must be linux")
    if plan.provider != provider:
        raise InvalidLinuxActionPlanError("plan provider does not match LinuxAdapter")
    if plan.request.action not in _ACTION_TOKENS:
        raise InvalidLinuxActionPlanError("unsupported Linux action")

    expected_operation, action_token, expected_state, success_verb = _ACTION_TOKENS[
        plan.request.action
    ]
    if plan.operation != expected_operation or _OPERATIONS[plan.request.action] != plan.operation:
        raise InvalidLinuxActionPlanError("plan operation does not match action")
    if not plan.requires_confirmation:
        raise InvalidLinuxActionPlanError("Linux systemd action must require confirmation")
    if not context.has_resource(plan.request.resource_id):
        raise InvalidLinuxActionPlanError("plan resource is not present in context")

    resource = context.resource(plan.request.resource_id)
    unit = _validated_unit_from_resource(target, resource)
    if unit is None:
        raise InvalidLinuxActionPlanError("plan resource is not a valid Linux service")

    metadata_unit = plan.metadata.get("unit")
    metadata_target = plan.metadata.get("ssh_target")
    metadata_host_id = plan.metadata.get("host_id")
    expected_host_id = f"linux:host:{target}"

    if metadata_unit != unit:
        raise InvalidLinuxActionPlanError("plan unit does not match resource")
    if metadata_target != target:
        raise InvalidLinuxActionPlanError("plan SSH target does not match adapter")
    if metadata_host_id != expected_host_id:
        raise InvalidLinuxActionPlanError("plan host id does not match adapter")
    if plan.request.resource_id != f"linux:service:{target}:{unit}":
        raise InvalidLinuxActionPlanError("plan resource id does not match unit")

    return unit, action_token, expected_state, success_verb


def _validated_unit_from_resource(target: str, resource: Resource) -> str | None:
    unit = _service_unit(target, resource)
    if unit is None or not _valid_service_unit(unit):
        return None
    return unit


def _exit_code(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise LinuxActionOutputError("systemd action exit code must be integer") from exc
    if result < 0:
        raise LinuxActionOutputError("systemd action exit code must be non-negative")
    return result


def _state(value: str, key: str) -> str:
    if not value or not _STATE_PATTERN.fullmatch(value):
        raise LinuxActionOutputError(f"systemd action state is invalid: {key}")
    return value


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, SshExecutableNotFoundError):
        return "SSH executable was not found"
    if isinstance(error, SshCommandTimeoutError):
        return "SSH command timed out during systemd action execution"
    if isinstance(error, SshCommandError):
        return f"SSH command failed during systemd action execution with exit code {error.return_code}"

    return "systemd action execution failed"
