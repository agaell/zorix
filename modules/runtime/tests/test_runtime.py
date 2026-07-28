from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "modules" / "core_model" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "plugin_loader" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "registry" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "scan_engine" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "runtime" / "src"))

from zorix_core_model import Adapter, Resource
from zorix_plugin_loader import PluginLoader
from zorix_registry import DuplicateAdapterError, Registry
from zorix_scan_engine import ScanStatus
from zorix_runtime import ZorixRuntime


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


if __name__ == "__main__":
    unittest.main()
