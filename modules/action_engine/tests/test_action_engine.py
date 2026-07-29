from __future__ import annotations

import copy
import unittest

from zorix_action_api import ActionContext
from zorix_action_engine import (
    ActionEngine,
    AmbiguousActionProviderError,
    InvalidActionProviderOutputError,
)
from zorix_action_model import (
    ActionPlan,
    ActionPlanStatus,
    ActionRequest,
    ActionRisk,
    ActionStep,
)
from zorix_core_model import Adapter, Resource
from zorix_registry import Registry


class StaticProvider(Adapter):
    def __init__(self, plan: ActionPlan | None) -> None:
        self.plan = plan
        self.requests: list[ActionRequest] = []

    def discover(self) -> list[Resource]:
        return []

    def plan_action(self, context: ActionContext, request: ActionRequest) -> ActionPlan | None:
        self.requests.append(request)
        return self.plan


class SecondStaticProvider(StaticProvider):
    pass


class FailingProvider(Adapter):
    def discover(self) -> list[Resource]:
        return []

    def plan_action(self, context: ActionContext, request: ActionRequest) -> ActionPlan | None:
        raise RuntimeError("provider failed")


class InvalidOutputProvider(Adapter):
    def __init__(self, output: object) -> None:
        self.output = output

    def discover(self) -> list[Resource]:
        return []

    def plan_action(self, context: ActionContext, request: ActionRequest) -> object:
        return self.output


class NotActionAdapter(Adapter):
    def discover(self) -> list[Resource]:
        return []


class ActionEngineTest(unittest.TestCase):
    def test_no_providers_returns_unsupported(self) -> None:
        result = ActionEngine(Registry()).plan([_resource("r1")], _request())

        self.assertIs(result.status, ActionPlanStatus.REJECTED)
        self.assertEqual(result.rejection.code, "action.unsupported")
        self.assertEqual(result.provider_count, 0)

    def test_missing_resource_returns_resource_not_found(self) -> None:
        result = ActionEngine(_registry(StaticProvider(_plan()))).plan([], _request())

        self.assertIs(result.status, ActionPlanStatus.REJECTED)
        self.assertEqual(result.rejection.code, "action.resource_not_found")
        self.assertEqual(result.provider_count, 1)

    def test_one_provider_returning_none_returns_unsupported(self) -> None:
        result = ActionEngine(_registry(StaticProvider(None))).plan([_resource("r1")], _request())

        self.assertIs(result.status, ActionPlanStatus.REJECTED)
        self.assertEqual(result.rejection.message, "No provider supports service.restart for this resource")

    def test_one_valid_provider_returns_ready(self) -> None:
        plan = _plan()
        result = ActionEngine(_registry(StaticProvider(plan))).plan([_resource("r1")], _request())

        self.assertIs(result.status, ActionPlanStatus.READY)
        self.assertIs(result.plan, plan)
        self.assertEqual(result.provider_count, 1)

    def test_multiple_providers_where_one_matches_and_order(self) -> None:
        first = StaticProvider(None)
        second = SecondStaticProvider(_plan())
        request = _request()

        result = ActionEngine(_registry(first, second)).plan([_resource("r1")], request)

        self.assertIs(result.status, ActionPlanStatus.READY)
        self.assertEqual(first.requests, [request])
        self.assertEqual(second.requests, [request])

    def test_provider_exception_propagates(self) -> None:
        with self.assertRaises(RuntimeError):
            ActionEngine(_registry(FailingProvider())).plan([_resource("r1")], _request())

    def test_invalid_output_raises(self) -> None:
        with self.assertRaises(InvalidActionProviderOutputError):
            ActionEngine(_registry(InvalidOutputProvider("bad"))).plan([_resource("r1")], _request())

    def test_plan_request_mismatch_raises(self) -> None:
        plan = _plan(request=ActionRequest("service.stop", "r1"))

        with self.assertRaises(InvalidActionProviderOutputError):
            ActionEngine(_registry(StaticProvider(plan))).plan([_resource("r1")], _request())

    def test_two_matching_plans_raise_ambiguous(self) -> None:
        with self.assertRaises(AmbiguousActionProviderError) as context:
            ActionEngine(_registry(StaticProvider(_plan()), SecondStaticProvider(_plan()))).plan(
                [_resource("r1")],
                _request(),
            )

        self.assertIn("service.restart", str(context.exception))
        self.assertIn("r1", str(context.exception))
        self.assertIn("2", str(context.exception))

    def test_registry_is_read_each_plan(self) -> None:
        registry = Registry()
        engine = ActionEngine(registry)

        first = engine.plan([_resource("r1")], _request())
        registry.register(StaticProvider(_plan()))
        second = engine.plan([_resource("r1")], _request())

        self.assertIs(first.status, ActionPlanStatus.REJECTED)
        self.assertIs(second.status, ActionPlanStatus.READY)

    def test_resources_and_request_are_not_changed_and_repeated_plan_identical(self) -> None:
        resources = [_resource("r1")]
        request = _request()
        before_resources = copy.deepcopy(resources)
        before_request = copy.deepcopy(request)
        engine = ActionEngine(_registry(StaticProvider(_plan())))

        first = engine.plan(resources, request)
        second = engine.plan(resources, request)

        self.assertEqual(first, second)
        self.assertEqual(resources, before_resources)
        self.assertEqual(request, before_request)

    def test_non_action_adapters_are_ignored(self) -> None:
        result = ActionEngine(_registry(NotActionAdapter())).plan([_resource("r1")], _request())

        self.assertEqual(result.provider_count, 0)


def _registry(*adapters: Adapter) -> Registry:
    registry = Registry()
    registry.register_many(adapters)
    return registry


def _request() -> ActionRequest:
    return ActionRequest("service.restart", "r1")


def _resource(resource_id: str) -> Resource:
    return Resource(resource_id, "service", resource_id, "active")


def _plan(request: ActionRequest | None = None) -> ActionPlan:
    request = _request() if request is None else request
    return ActionPlan(
        source="test",
        provider="provider.Class",
        request=request,
        resource_name="r1",
        operation="test.operation",
        risk=ActionRisk.MEDIUM,
        requires_confirmation=True,
        summary="Plan action",
        steps=(ActionStep(1, "step.one", "First step"),),
    )


if __name__ == "__main__":
    unittest.main()
