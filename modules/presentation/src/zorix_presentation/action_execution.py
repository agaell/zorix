from __future__ import annotations

from zorix_action_model import ActionExecutionResult, ActionExecutionStatus


class ActionExecutionConsoleRenderer:
    def render(self, result: ActionExecutionResult) -> str:
        if result.status is ActionExecutionStatus.REJECTED:
            return "\n".join(_rejected_lines(result)) + "\n"

        return "\n".join(_executed_lines(result)) + "\n"


def _executed_lines(result: ActionExecutionResult) -> list[str]:
    plan = result.plan
    if plan is None:
        raise ValueError("executed result requires plan")

    return [
        f"Action execution: {result.status.value}",
        "Executed: yes",
        f"Action: {result.request.action}",
        f"Resource: {plan.resource_name}",
        f"Resource ID: {result.request.resource_id}",
        f"Provider: {plan.provider}",
        f"Operation: {plan.operation}",
        f"Risk: {plan.risk.value}",
        "Confirmed: yes",
        f"Previous state: {_state(result.previous_state)}",
        f"Current state: {_state(result.current_state)}",
        f"Changed: {_yes_no(result.changed)}",
        f"Verified: {_yes_no(result.verified)}",
        f"Message: {result.message}",
    ]


def _rejected_lines(result: ActionExecutionResult) -> list[str]:
    rejection = result.rejection
    if rejection is None:
        raise ValueError("REJECTED result requires rejection")

    lines = [
        "Action execution: REJECTED",
        "Executed: no",
        f"Action: {result.request.action}",
    ]

    if result.plan is not None:
        lines.extend(
            [
                f"Resource: {result.plan.resource_name}",
                f"Resource ID: {result.request.resource_id}",
                f"Provider: {result.plan.provider}",
                f"Operation: {result.plan.operation}",
                f"Risk: {result.plan.risk.value}",
            ]
        )
    else:
        lines.append(f"Resource ID: {result.request.resource_id}")

    lines.extend(
        [
            f"Reason: {rejection.code}",
            f"Message: {rejection.message}",
        ]
    )
    return lines


def _state(value: str | None) -> str:
    return value if value is not None else "unknown"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
