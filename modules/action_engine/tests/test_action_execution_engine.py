from __future__ import annotations

import unittest

from zorix_action_api import ActionContext
from zorix_action_engine import (
    ActionExecutionEngine,
    ActionExecutorNotFoundError,
    AmbiguousActionExecutorError,
    InvalidActionExecutorOutputError,
)
from zorix_action_model import (
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionPlan,
    ActionPlanStatus,
    ActionRequest,
    ActionRisk,
    ActionStep,
)
from zorix_core_model import Adapter, Resource
from zorix_registry import Registry


class PlanningAdapter(Adapter):
    def __init__(self, plan: ActionPlan | None) -> None:
        self.plan = plan
        self.execute_calls = 0

    def discover(self) -> list[Resource]:
        return []

    def plan_action(self, context: ActionContext, request: ActionRequest) -> ActionPlan | None:
        return self.plan

    def execute_action(
        self,
        context: ActionContext,
        plan: ActionPlan,
    ) -> ActionExecutionResult:
        self.execute_calls += 1
        return ActionExecutionResult(
            ActionExecutionStatus.SUCCESS,
            plan.request,
            plan,
            "inactive",
            "active",
            True,
            True,
            "executed",
        )


class SecondPlanningAdapter(PlanningAdapter):
    pass


class PlanOnlyAdapter(Adapter):
    def __init__(self, plan: ActionPlan) -> None:
        self.plan = plan

    def discover(self) -> list[Resource]:
        return []

    def plan_action(self, context: ActionContext, request: ActionRequest) -> ActionPlan | None:
        return self.plan


class InvalidExecutorAdapter(PlanningAdapter):
    def __init__(self, plan: ActionPlan, output: object) -> None:
        super().__init__(plan)
        self.output = output

    def execute_action(self, context: ActionContext, plan: ActionPlan) -> object:
        return self.output


class RequestMismatchExecutorAdapter(PlanningAdapter):
    def execute_action(
        self,
        context: ActionContext,
        plan: ActionPlan,
    ) -> ActionExecutionResult:
        return ActionExecutionResult(
            ActionExecutionStatus.SUCCESS,
            ActionRequest("service.restart", "other"),
            _plan(
                provider=_provider_name(RequestMismatchExecutorAdapter),
                request=ActionRequest("service.restart", "other"),
                requires_confirmation=False,
            ),
            "inactive",
            "active",
            True,
            True,
            "executed",
        )


class PlanMismatchExecutorAdapter(PlanningAdapter):
    def execute_action(
        self,
        context: ActionContext,
        plan: ActionPlan,
    ) -> ActionExecutionResult:
        return ActionExecutionResult(
            ActionExecutionStatus.SUCCESS,
            plan.request,
            _plan(
                provider=_provider_name(PlanMismatchExecutorAdapter),
                operation="other.operation",
                requires_confirmation=False,
            ),
            "inactive",
            "active",
            True,
            True,
            "executed",
        )


class RejectedExecutorAdapter(PlanningAdapter):
    def execute_action(
        self,
        context: ActionContext,
        plan: ActionPlan,
    ) -> ActionExecutionResult:
        from zorix_action_model import ActionExecutionRejection

        return ActionExecutionResult(
            ActionExecutionStatus.REJECTED,
            plan.request,
            plan,
            None,
            None,
            False,
            False,
            "rejected",
            rejection=ActionExecutionRejection("action.rejected", "rejected"),
        )


class FailingExecutorAdapter(PlanningAdapter):
    def execute_action(self, context: ActionContext, plan: ActionPlan) -> ActionExecutionResult:
        raise RuntimeError("execution failed")


class ActionExecutionEngineTest(unittest.TestCase):
    def test_planning_rejection_returns_execution_rejection(self) -> None:
        result = ActionExecutionEngine(Registry()).execute([_resource()], _request())

        self.assertIs(result.status, ActionExecutionStatus.REJECTED)
        self.assertEqual(result.rejection.code, "action.unsupported")
        self.assertIsNone(result.plan)

    def test_confirmation_required_rejects_before_executor_call(self) -> None:
        adapter = PlanningAdapter(_plan(provider=_provider_name(PlanningAdapter)))
        result = ActionExecutionEngine(_registry(adapter)).execute([_resource()], _request())

        self.assertIs(result.status, ActionExecutionStatus.REJECTED)
        self.assertEqual(result.rejection.code, "action.confirmation_required")
        self.assertEqual(adapter.execute_calls, 0)

    def test_confirmed_execution_delegates_to_matching_executor(self) -> None:
        plan = _plan(provider=_provider_name(PlanningAdapter))
        adapter = PlanningAdapter(plan)

        result = ActionExecutionEngine(_registry(adapter)).execute(
            [_resource()],
            _request(),
            confirmed=True,
        )

        self.assertIs(result.status, ActionExecutionStatus.SUCCESS)
        self.assertEqual(adapter.execute_calls, 1)

    def test_executor_not_found(self) -> None:
        plan = _plan(provider="missing.Executor", requires_confirmation=False)

        with self.assertRaises(ActionExecutorNotFoundError):
            ActionExecutionEngine(_registry(PlanOnlyAdapter(plan))).execute(
                [_resource()],
                _request(),
                confirmed=True,
            )

    def test_ambiguous_executor(self) -> None:
        plan = _plan(provider=_provider_name(PlanningAdapter), requires_confirmation=False)

        class TwinExecutor(PlanningAdapter):
            pass

        TwinExecutor.__module__ = PlanningAdapter.__module__
        TwinExecutor.__qualname__ = PlanningAdapter.__qualname__

        with self.assertRaises(AmbiguousActionExecutorError):
            ActionExecutionEngine(
                _registry(PlanningAdapter(plan), TwinExecutor(None))
            ).execute([_resource()], _request(), confirmed=True)

    def test_invalid_executor_output(self) -> None:
        plan = _plan(provider=_provider_name(InvalidExecutorAdapter), requires_confirmation=False)

        with self.assertRaises(InvalidActionExecutorOutputError):
            ActionExecutionEngine(_registry(InvalidExecutorAdapter(plan, "bad"))).execute(
                [_resource()],
                _request(),
                confirmed=True,
            )

    def test_request_mismatch_executor_output_raises(self) -> None:
        plan = _plan(
            provider=_provider_name(RequestMismatchExecutorAdapter),
            requires_confirmation=False,
        )

        with self.assertRaises(InvalidActionExecutorOutputError):
            ActionExecutionEngine(_registry(RequestMismatchExecutorAdapter(plan))).execute(
                [_resource()],
                _request(),
                confirmed=True,
            )

    def test_plan_mismatch_executor_output_raises(self) -> None:
        plan = _plan(
            provider=_provider_name(PlanMismatchExecutorAdapter),
            requires_confirmation=False,
        )

        with self.assertRaises(InvalidActionExecutorOutputError):
            ActionExecutionEngine(_registry(PlanMismatchExecutorAdapter(plan))).execute(
                [_resource()],
                _request(),
                confirmed=True,
            )

    def test_executor_must_not_return_rejected(self) -> None:
        plan = _plan(
            provider=_provider_name(RejectedExecutorAdapter),
            requires_confirmation=False,
        )

        with self.assertRaises(InvalidActionExecutorOutputError):
            ActionExecutionEngine(_registry(RejectedExecutorAdapter(plan))).execute(
                [_resource()],
                _request(),
                confirmed=True,
            )

    def test_executor_exception_propagates(self) -> None:
        plan = _plan(provider=_provider_name(FailingExecutorAdapter), requires_confirmation=False)

        with self.assertRaises(RuntimeError):
            ActionExecutionEngine(_registry(FailingExecutorAdapter(plan))).execute(
                [_resource()],
                _request(),
                confirmed=True,
            )


def _registry(*adapters: Adapter) -> Registry:
    registry = Registry()
    registry.register_many(adapters)
    return registry


def _resource() -> Resource:
    return Resource("r1", "service", "r1", "active")


def _request() -> ActionRequest:
    return ActionRequest("service.restart", "r1")


def _plan(
    *,
    provider: str,
    requires_confirmation: bool = True,
    request: ActionRequest | None = None,
    operation: str = "test.operation",
) -> ActionPlan:
    request = _request() if request is None else request
    return ActionPlan(
        source="test",
        provider=provider,
        request=request,
        resource_name="r1",
        operation=operation,
        risk=ActionRisk.MEDIUM,
        requires_confirmation=requires_confirmation,
        summary="Plan action",
        steps=(ActionStep(1, "step.one", "First step"),),
    )


def _provider_name(provider_type: type[object]) -> str:
    return f"{provider_type.__module__}.{provider_type.__qualname__}"


if __name__ == "__main__":
    unittest.main()
