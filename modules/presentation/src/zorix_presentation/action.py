from __future__ import annotations

from zorix_action_model import ActionPlanResult, ActionPlanStatus


class ActionPlanConsoleRenderer:
    def render(self, result: ActionPlanResult) -> str:
        if result.status is ActionPlanStatus.READY:
            return "\n".join(_ready_lines(result)) + "\n"

        return "\n".join(_rejected_lines(result)) + "\n"


def _ready_lines(result: ActionPlanResult) -> list[str]:
    plan = result.plan
    if plan is None:
        raise ValueError("READY result requires plan")

    lines = [
        "Action planning: READY",
        "Dry run: yes",
        f"Action: {result.request.action}",
        f"Resource: {plan.resource_name}",
        f"Resource ID: {result.request.resource_id}",
        f"Provider: {plan.provider}",
        f"Operation: {plan.operation}",
        f"Risk: {plan.risk.value}",
        f"Confirmation required: {_yes_no(plan.requires_confirmation)}",
        f"Summary: {plan.summary}",
        "",
        "Steps:",
    ]
    lines.extend(f"{step.position}. {step.description}" for step in plan.steps)
    return lines


def _rejected_lines(result: ActionPlanResult) -> list[str]:
    rejection = result.rejection
    if rejection is None:
        raise ValueError("REJECTED result requires rejection")

    return [
        "Action planning: REJECTED",
        "Dry run: yes",
        f"Action: {result.request.action}",
        f"Resource ID: {result.request.resource_id}",
        f"Reason: {rejection.code}",
        f"Message: {rejection.message}",
    ]


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
