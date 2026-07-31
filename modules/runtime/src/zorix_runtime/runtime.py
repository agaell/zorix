from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from zorix_action_engine import ActionEngine, ActionExecutionEngine
from zorix_action_model import ActionExecutionResult, ActionPlanResult, ActionRequest
from zorix_core_model import Adapter, Resource
from zorix_health_engine import HealthEngine, HealthResult
from zorix_plugin_loader import PluginLoader
from zorix_registry import Registry
from zorix_scan_engine import ScanEngine, ScanResult
from zorix_topology_engine import TopologyEngine, TopologyResult


class ZorixRuntime:
    def __init__(
        self,
        plugin_loader: PluginLoader | None = None,
        registry: Registry | None = None,
    ) -> None:
        self._plugin_loader = plugin_loader if plugin_loader is not None else PluginLoader()
        self._registry = registry if registry is not None else Registry()
        self._scan_engine = ScanEngine(self._registry)
        self._action_engine = ActionEngine(self._registry)
        self._action_execution_engine = ActionExecutionEngine(self._registry)
        self._health_engine = HealthEngine(self._registry)
        self._topology_engine = TopologyEngine(self._registry)

    def load_plugins(self, path: str | Path) -> tuple[Adapter, ...]:
        adapters = tuple(self._plugin_loader.load(path))
        self._registry.register_many(adapters)
        return adapters

    def scan(self, *, continue_on_error: bool = False) -> ScanResult:
        return self._scan_engine.scan(continue_on_error=continue_on_error)

    def build_topology(
        self,
        resources: Iterable[Resource],
        *,
        continue_on_error: bool = False,
    ) -> TopologyResult:
        return self._topology_engine.build(
            resources,
            continue_on_error=continue_on_error,
        )

    def evaluate_health(
        self,
        resources: Iterable[Resource],
        *,
        continue_on_error: bool = False,
    ) -> HealthResult:
        return self._health_engine.evaluate(
            resources,
            continue_on_error=continue_on_error,
        )

    def plan_action(
        self,
        resources: Iterable[Resource],
        request: ActionRequest,
    ) -> ActionPlanResult:
        return self._action_engine.plan(resources, request)

    def execute_action(
        self,
        resources: Iterable[Resource],
        request: ActionRequest,
        *,
        confirmed: bool = False,
    ) -> ActionExecutionResult:
        return self._action_execution_engine.execute(
            resources,
            request,
            confirmed=confirmed,
        )

    def adapters(self) -> tuple[Adapter, ...]:
        return self._registry.adapters()

    def clear(self) -> None:
        self._registry.clear()
