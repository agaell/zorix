from __future__ import annotations

from collections.abc import Iterable

from zorix_action_api import ActionContext, ActionExecutor
from zorix_action_model import (
    ActionExecutionRejection,
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionPlan,
    ActionPlanStatus,
    ActionRequest,
)
from zorix_core_model import Resource
from zorix_registry import Registry

from .engine import _plan_with_context, _provider_name
from .errors import (
    ActionExecutorNotFoundError,
    AmbiguousActionExecutorError,
    InvalidActionExecutorOutputError,
)


class ActionExecutionEngine:
    def __init__(self, registry: Registry) -> None:
        if registry is None:
            raise TypeError("registry is required")

        self._registry = registry

    def execute(
        self,
        resources: Iterable[Resource],
        request: ActionRequest,
        *,
        confirmed: bool = False,
    ) -> ActionExecutionResult:
        if not isinstance(request, ActionRequest):
            raise TypeError("request must be ActionRequest")
        if not isinstance(confirmed, bool):
            raise TypeError("confirmed must be bool")

        context = ActionContext(resources)
        plan_result = _plan_with_context(self._registry, context, request)

        if plan_result.status is ActionPlanStatus.REJECTED:
            rejection = plan_result.rejection
            if rejection is None:
                raise InvalidActionExecutorOutputError(
                    "zorix_action_engine.ActionEngine",
                    "REJECTED planning result requires rejection",
                )
            return ActionExecutionResult(
                status=ActionExecutionStatus.REJECTED,
                request=request,
                plan=None,
                previous_state=None,
                current_state=None,
                changed=False,
                verified=False,
                message=rejection.message,
                rejection=ActionExecutionRejection(rejection.code, rejection.message),
            )

        plan = plan_result.plan
        if not isinstance(plan, ActionPlan):
            raise InvalidActionExecutorOutputError(
                "zorix_action_engine.ActionEngine",
                "READY planning result requires plan",
            )

        if plan.requires_confirmation and not confirmed:
            message = "Explicit confirmation is required before executing this action"
            return ActionExecutionResult(
                status=ActionExecutionStatus.REJECTED,
                request=request,
                plan=plan,
                previous_state=None,
                current_state=None,
                changed=False,
                verified=False,
                message=message,
                rejection=ActionExecutionRejection(
                    "action.confirmation_required",
                    message,
                ),
            )

        executor = _select_executor(self._registry.adapters(), plan.provider)
        result = executor.execute_action(context, plan)
        executor_name = _provider_name(executor)

        if not isinstance(result, ActionExecutionResult):
            raise InvalidActionExecutorOutputError(executor_name, type(result).__name__)
        if result.request != request:
            raise InvalidActionExecutorOutputError(
                executor_name,
                "result request does not match original request",
            )
        if result.plan != plan:
            raise InvalidActionExecutorOutputError(
                executor_name,
                "result plan does not match selected plan",
            )
        if result.status is ActionExecutionStatus.REJECTED:
            raise InvalidActionExecutorOutputError(
                executor_name,
                "executor must not return REJECTED",
            )

        return result


def _select_executor(
    adapters: tuple[object, ...],
    provider_name: str,
) -> ActionExecutor:
    executors = tuple(
        adapter
        for adapter in adapters
        if isinstance(adapter, ActionExecutor) and _provider_name(adapter) == provider_name
    )

    if not executors:
        raise ActionExecutorNotFoundError(provider_name)
    if len(executors) > 1:
        raise AmbiguousActionExecutorError(provider_name, len(executors))

    return executors[0]
