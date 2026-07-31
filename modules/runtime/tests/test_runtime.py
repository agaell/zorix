from __future__ import annotations

from collections.abc import Iterator
import unittest
from pathlib import Path
from unittest.mock import patch

from zorix_action_model import (
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionPlan,
    ActionPlanResult,
    ActionPlanStatus,
    ActionRejection,
    ActionRequest,
    ActionRisk,
    ActionStep,
)
from zorix_core_model import Adapter, Resource
from zorix_health_engine import HealthResult, HealthStatus
from zorix_health_model import HealthLevel
from zorix_plugin_loader import PluginLoader
from zorix_registry import DuplicateAdapterError, Registry
from zorix_resource_graph import ResourceGraphBuilder
from zorix_scan_engine import ScanStatus
from zorix_runtime import ZorixRuntime
from zorix_topology_engine import TopologyResult, TopologyStatus


def _resource(resource_id: str, resource_type: str) -> Resource:
    return Resource(
        id=resource_id,
        type=resource_type,
        name=resource_id,
        state="active",
    )


class StaticAdapter(Adapter):
    def __init__(self, resources: list[Resource]) -> None:
        self._resources = resources

    def discover(self) -> list[Resource]:
        return list(self._resources)


class FailingAdapter(Adapter):
    def discover(self) -> list[Resource]:
        raise RuntimeError("adapter failed")


class CountingAdapter(Adapter):
    def __init__(self) -> None:
        self.discover_calls = 0

    def discover(self) -> list[Resource]:
        self.discover_calls += 1
        return []


class CountingResources:
    def __init__(self, resources: list[Resource]) -> None:
        self._resources = resources
        self.iteration_count = 0

    def __iter__(self) -> Iterator[Resource]:
        self.iteration_count += 1
        return iter(self._resources)


class RecordingPluginLoader(PluginLoader):
    def __init__(self, adapters: list[Adapter] | None = None, error: Exception | None = None) -> None:
        self.adapters = adapters or []
        self.error = error
        self.loaded_paths: list[Path] = []

    def load(self, path: str | Path) -> list[Adapter]:
        self.loaded_paths.append(Path(path))
        if self.error is not None:
            raise self.error
        return list(self.adapters)


class RuntimeTest(unittest.TestCase):
    def test_accepts_plugin_loader_and_registry_dependencies(self) -> None:
        adapter = StaticAdapter([_resource("service-1", "service")])
        loader = RecordingPluginLoader([adapter])
        registry = Registry()
        runtime = ZorixRuntime(plugin_loader=loader, registry=registry)

        loaded_adapters = runtime.load_plugins("adapters")

        self.assertEqual(loaded_adapters, (adapter,))
        self.assertEqual(registry.adapters(), (adapter,))
        self.assertEqual(loader.loaded_paths, [Path("adapters")])

    def test_creates_default_dependencies(self) -> None:
        runtime = ZorixRuntime()

        result = runtime.scan()

        self.assertEqual(runtime.adapters(), ())
        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(result.resources, ())
        self.assertEqual(result.errors, ())

    def test_has_public_build_topology_method(self) -> None:
        runtime = ZorixRuntime()

        self.assertTrue(callable(runtime.build_topology))

    def test_load_plugins_delegates_loading_and_registration(self) -> None:
        adapter = StaticAdapter([_resource("service-1", "service")])
        loader = RecordingPluginLoader([adapter])
        runtime = ZorixRuntime(plugin_loader=loader, registry=Registry())

        loaded_adapters = runtime.load_plugins("plugins")

        self.assertEqual(loaded_adapters, (adapter,))
        self.assertEqual(runtime.adapters(), (adapter,))
        self.assertEqual(loader.loaded_paths, [Path("plugins")])

    def test_scan_delegates_to_scan_engine(self) -> None:
        adapter = StaticAdapter([_resource("service-1", "service")])
        registry = Registry()
        registry.register(adapter)
        runtime = ZorixRuntime(plugin_loader=RecordingPluginLoader(), registry=registry)

        result = runtime.scan()

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual([resource.id for resource in result.resources], ["service-1"])

    def test_adapters_returns_tuple(self) -> None:
        runtime = ZorixRuntime(plugin_loader=RecordingPluginLoader(), registry=Registry())

        self.assertIsInstance(runtime.adapters(), tuple)

    def test_clear_clears_registry(self) -> None:
        adapter = StaticAdapter([_resource("service-1", "service")])
        runtime = ZorixRuntime(plugin_loader=RecordingPluginLoader([adapter]), registry=Registry())
        runtime.load_plugins("plugins")

        runtime.clear()

        self.assertEqual(runtime.adapters(), ())

    def test_plugin_loader_errors_are_not_suppressed(self) -> None:
        error = RuntimeError("loader failed")
        runtime = ZorixRuntime(plugin_loader=RecordingPluginLoader(error=error), registry=Registry())

        with self.assertRaises(RuntimeError) as context:
            runtime.load_plugins("plugins")

        self.assertIs(context.exception, error)

    def test_duplicate_adapter_error_is_not_suppressed(self) -> None:
        adapter = StaticAdapter([_resource("service-1", "service")])
        runtime = ZorixRuntime(plugin_loader=RecordingPluginLoader([adapter]), registry=Registry())
        runtime.load_plugins("plugins")

        with self.assertRaises(DuplicateAdapterError):
            runtime.load_plugins("plugins")

    def test_continue_on_error_is_passed_to_scan_engine(self) -> None:
        registry = Registry()
        registry.register(FailingAdapter())
        runtime = ZorixRuntime(plugin_loader=RecordingPluginLoader(), registry=registry)

        result = runtime.scan(continue_on_error=True)

        self.assertIs(result.status, ScanStatus.FAILED)
        self.assertEqual(len(result.errors), 1)

    def test_build_topology_delegates_resources_and_returns_result(self) -> None:
        expected_result = _topology_result()
        resources = [_resource("service-1", "service")]

        with patch("zorix_runtime.runtime.TopologyEngine") as topology_engine_class:
            topology_engine = topology_engine_class.return_value
            topology_engine.build.return_value = expected_result
            runtime = ZorixRuntime()

            result = runtime.build_topology(resources)

        topology_engine.build.assert_called_once_with(resources, continue_on_error=False)
        self.assertIs(result, expected_result)

    def test_build_topology_does_not_iterate_resources_before_delegation(self) -> None:
        resources = CountingResources([_resource("service-1", "service")])

        with patch("zorix_runtime.runtime.TopologyEngine") as topology_engine_class:
            topology_engine = topology_engine_class.return_value
            runtime = ZorixRuntime()

            runtime.build_topology(resources)

        topology_engine.build.assert_called_once_with(resources, continue_on_error=False)
        self.assertEqual(resources.iteration_count, 0)

    def test_build_topology_passes_continue_on_error(self) -> None:
        with patch("zorix_runtime.runtime.TopologyEngine") as topology_engine_class:
            topology_engine = topology_engine_class.return_value
            runtime = ZorixRuntime()

            runtime.build_topology([], continue_on_error=True)

        topology_engine.build.assert_called_once_with([], continue_on_error=True)

    def test_build_topology_does_not_suppress_topology_engine_errors(self) -> None:
        error = RuntimeError("topology failed")

        with patch("zorix_runtime.runtime.TopologyEngine") as topology_engine_class:
            topology_engine = topology_engine_class.return_value
            topology_engine.build.side_effect = error
            runtime = ZorixRuntime()

            with self.assertRaises(RuntimeError) as context:
                runtime.build_topology([])

        self.assertIs(context.exception, error)

    def test_build_topology_does_not_call_scan_engine_or_adapter_discover(self) -> None:
        adapter = CountingAdapter()
        registry = Registry()
        registry.register(adapter)

        with patch("zorix_runtime.runtime.ScanEngine") as scan_engine_class, patch(
            "zorix_runtime.runtime.TopologyEngine"
        ) as topology_engine_class:
            runtime = ZorixRuntime(registry=registry)

            runtime.build_topology([])

        scan_engine_class.return_value.scan.assert_not_called()
        topology_engine_class.return_value.build.assert_called_once_with(
            [],
            continue_on_error=False,
        )
        self.assertEqual(adapter.discover_calls, 0)

    def test_scan_does_not_call_topology_engine(self) -> None:
        with patch("zorix_runtime.runtime.TopologyEngine") as topology_engine_class:
            runtime = ZorixRuntime()

            runtime.scan()

        topology_engine_class.return_value.build.assert_not_called()

    def test_evaluate_health_delegates_resources_and_returns_result(self) -> None:
        expected_result = _health_result()
        resources = [_resource("service-1", "service")]

        with patch("zorix_runtime.runtime.HealthEngine") as health_engine_class:
            health_engine = health_engine_class.return_value
            health_engine.evaluate.return_value = expected_result
            runtime = ZorixRuntime()

            result = runtime.evaluate_health(resources)

        health_engine.evaluate.assert_called_once_with(resources, continue_on_error=False)
        self.assertIs(result, expected_result)

    def test_evaluate_health_uses_runtime_registry(self) -> None:
        registry = Registry()

        with patch("zorix_runtime.runtime.HealthEngine") as health_engine_class:
            runtime = ZorixRuntime(registry=registry)

        health_engine_class.assert_called_once_with(registry)
        self.assertTrue(callable(runtime.evaluate_health))

    def test_evaluate_health_passes_continue_on_error(self) -> None:
        with patch("zorix_runtime.runtime.HealthEngine") as health_engine_class:
            health_engine = health_engine_class.return_value
            runtime = ZorixRuntime()

            runtime.evaluate_health([], continue_on_error=True)

        health_engine.evaluate.assert_called_once_with([], continue_on_error=True)

    def test_evaluate_health_does_not_call_scan_or_topology(self) -> None:
        with patch("zorix_runtime.runtime.ScanEngine") as scan_engine_class, patch(
            "zorix_runtime.runtime.TopologyEngine"
        ) as topology_engine_class:
            runtime = ZorixRuntime()

            runtime.evaluate_health([])

        scan_engine_class.return_value.scan.assert_not_called()
        topology_engine_class.return_value.build.assert_not_called()

    def test_plan_action_delegates_resources_and_request_and_returns_result(self) -> None:
        expected_result = _action_result()
        resources = [_resource("service-1", "service")]
        request = ActionRequest("service.restart", "service-1")

        with patch("zorix_runtime.runtime.ActionEngine") as action_engine_class:
            action_engine = action_engine_class.return_value
            action_engine.plan.return_value = expected_result
            runtime = ZorixRuntime()

            result = runtime.plan_action(resources, request)

        action_engine.plan.assert_called_once_with(resources, request)
        self.assertIs(result, expected_result)

    def test_plan_action_uses_runtime_registry_and_does_not_call_other_engines(self) -> None:
        registry = Registry()
        request = ActionRequest("service.restart", "service-1")

        with patch("zorix_runtime.runtime.ActionEngine") as action_engine_class, patch(
            "zorix_runtime.runtime.ScanEngine"
        ) as scan_engine_class, patch("zorix_runtime.runtime.TopologyEngine") as topology_engine_class, patch(
            "zorix_runtime.runtime.HealthEngine"
        ) as health_engine_class:
            runtime = ZorixRuntime(registry=registry)

            runtime.plan_action([], request)

        action_engine_class.assert_called_once_with(registry)
        action_engine_class.return_value.plan.assert_called_once_with([], request)
        scan_engine_class.return_value.scan.assert_not_called()
        topology_engine_class.return_value.build.assert_not_called()
        health_engine_class.return_value.evaluate.assert_not_called()

    def test_execute_action_delegates_resources_request_and_confirmation(self) -> None:
        resources = [_resource("service-1", "service")]
        request = ActionRequest("service.restart", "service-1")
        expected_result = _execution_result(request)

        with patch("zorix_runtime.runtime.ActionExecutionEngine") as execution_engine_class:
            execution_engine = execution_engine_class.return_value
            execution_engine.execute.return_value = expected_result
            runtime = ZorixRuntime()

            result = runtime.execute_action(resources, request, confirmed=True)

        execution_engine.execute.assert_called_once_with(
            resources,
            request,
            confirmed=True,
        )
        self.assertIs(result, expected_result)

    def test_execute_action_uses_runtime_registry(self) -> None:
        registry = Registry()

        with patch("zorix_runtime.runtime.ActionExecutionEngine") as execution_engine_class:
            runtime = ZorixRuntime(registry=registry)

        execution_engine_class.assert_called_once_with(registry)
        self.assertTrue(callable(runtime.execute_action))

    def test_execute_action_does_not_call_scan_topology_health_or_discover(self) -> None:
        adapter = CountingAdapter()
        registry = Registry()
        registry.register(adapter)
        request = ActionRequest("service.restart", "service-1")

        with patch("zorix_runtime.runtime.ActionExecutionEngine") as execution_engine_class, patch(
            "zorix_runtime.runtime.ScanEngine"
        ) as scan_engine_class, patch("zorix_runtime.runtime.TopologyEngine") as topology_engine_class, patch(
            "zorix_runtime.runtime.HealthEngine"
        ) as health_engine_class:
            runtime = ZorixRuntime(registry=registry)

            runtime.execute_action([], request)

        execution_engine_class.return_value.execute.assert_called_once_with(
            [],
            request,
            confirmed=False,
        )
        scan_engine_class.return_value.scan.assert_not_called()
        topology_engine_class.return_value.build.assert_not_called()
        health_engine_class.return_value.evaluate.assert_not_called()
        self.assertEqual(adapter.discover_calls, 0)


def _topology_result() -> TopologyResult:
    return TopologyResult(
        status=TopologyStatus.SUCCESS,
        graph=ResourceGraphBuilder().build(),
        errors=(),
        provider_count=0,
        successful_provider_count=0,
    )


def _health_result() -> HealthResult:
    return HealthResult(
        status=HealthStatus.SUCCESS,
        level=HealthLevel.HEALTHY,
        findings=(),
        errors=(),
        provider_count=0,
        successful_provider_count=0,
        resource_count=0,
    )


def _action_result() -> ActionPlanResult:
    return ActionPlanResult(
        status=ActionPlanStatus.REJECTED,
        request=ActionRequest("service.restart", "service-1"),
        rejection=ActionRejection("action.unsupported", "unsupported"),
    )


def _execution_result(request: ActionRequest) -> ActionExecutionResult:
    plan = ActionPlan(
        "test",
        "provider.Class",
        request,
        "service-1",
        "test.operation",
        ActionRisk.MEDIUM,
        True,
        "Plan action",
        (ActionStep(1, "step.one", "First step"),),
    )
    return ActionExecutionResult(
        ActionExecutionStatus.SUCCESS,
        request,
        plan,
        "inactive",
        "active",
        True,
        True,
        "executed",
    )


if __name__ == "__main__":
    unittest.main()
