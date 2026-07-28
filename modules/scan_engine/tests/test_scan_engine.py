from __future__ import annotations

from dataclasses import FrozenInstanceError
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "modules" / "core_model" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "registry" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "scan_engine" / "src"))

from zorix_core_model import Adapter, Resource
from zorix_registry import Registry
from zorix_scan_engine import AdapterScanError, ScanEngine, ScanResult, ScanStatus


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


class AnotherStaticAdapter(Adapter):
    def __init__(self, resources: list[Resource]) -> None:
        self._resources = resources

    def discover(self) -> list[Resource]:
        return list(self._resources)


class FailingAdapter(Adapter):
    def __init__(self, error: Exception) -> None:
        self.error = error

    def discover(self) -> list[Resource]:
        raise self.error


class AnotherFailingAdapter(Adapter):
    def __init__(self, error: Exception) -> None:
        self.error = error

    def discover(self) -> list[Resource]:
        raise self.error


class ScanEngineTest(unittest.TestCase):
    def test_scans_single_adapter_successfully(self) -> None:
        registry = Registry()
        registry.register(StaticAdapter([_resource("service-1", "service")]))

        result = ScanEngine(registry).scan()

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertTrue(result.succeeded)
        self.assertEqual([resource.id for resource in result.resources], ["service-1"])
        self.assertEqual(result.errors, ())

    def test_scans_multiple_adapters_successfully(self) -> None:
        registry = Registry()
        registry.register_many(
            [
                StaticAdapter([_resource("service-1", "service")]),
                AnotherStaticAdapter([_resource("user-1", "user")]),
            ]
        )

        result = ScanEngine(registry).scan()

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual([resource.id for resource in result.resources], ["service-1", "user-1"])

    def test_preserves_resource_order(self) -> None:
        registry = Registry()
        registry.register_many(
            [
                StaticAdapter(
                    [
                        _resource("service-1", "service"),
                        _resource("container-1", "container"),
                    ]
                ),
                AnotherStaticAdapter([_resource("user-1", "user")]),
            ]
        )

        result = ScanEngine(registry).scan()

        self.assertEqual([resource.id for resource in result.resources], ["service-1", "container-1", "user-1"])

    def test_empty_registry_returns_success_with_empty_tuples(self) -> None:
        result = ScanEngine(Registry()).scan()

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(result.resources, ())
        self.assertEqual(result.errors, ())

    def test_fail_fast_passes_original_exception(self) -> None:
        registry = Registry()
        error = RuntimeError("adapter failed")
        registry.register(FailingAdapter(error))

        with self.assertRaises(RuntimeError) as context:
            ScanEngine(registry).scan()

        self.assertIs(context.exception, error)

    def test_continue_on_error_continues_scanning(self) -> None:
        registry = Registry()
        registry.register_many(
            [
                FailingAdapter(RuntimeError("adapter failed")),
                StaticAdapter([_resource("service-1", "service")]),
            ]
        )

        result = ScanEngine(registry).scan(continue_on_error=True)

        self.assertEqual([resource.id for resource in result.resources], ["service-1"])
        self.assertEqual(len(result.errors), 1)

    def test_partial_status_when_errors_and_resources_exist(self) -> None:
        registry = Registry()
        registry.register_many(
            [
                FailingAdapter(RuntimeError("adapter failed")),
                StaticAdapter([_resource("service-1", "service")]),
            ]
        )

        result = ScanEngine(registry).scan(continue_on_error=True)

        self.assertIs(result.status, ScanStatus.PARTIAL)
        self.assertTrue(result.partial)

    def test_failed_status_when_all_adapters_fail(self) -> None:
        registry = Registry()
        registry.register_many(
            [
                FailingAdapter(RuntimeError("first failed")),
                AnotherFailingAdapter(ValueError("second failed")),
            ]
        )

        result = ScanEngine(registry).scan(continue_on_error=True)

        self.assertIs(result.status, ScanStatus.FAILED)
        self.assertTrue(result.failed)
        self.assertEqual(result.resources, ())
        self.assertEqual(len(result.errors), 2)

    def test_adapter_scan_error_content(self) -> None:
        registry = Registry()
        registry.register(FailingAdapter(RuntimeError("adapter failed")))

        result = ScanEngine(registry).scan(continue_on_error=True)
        error = result.errors[0]

        self.assertEqual(error.adapter, f"{FailingAdapter.__module__}.{FailingAdapter.__qualname__}")
        self.assertEqual(error.error_type, "RuntimeError")
        self.assertEqual(error.message, "adapter failed")

    def test_scan_result_and_adapter_scan_error_are_immutable(self) -> None:
        result = ScanResult(status=ScanStatus.SUCCESS, resources=(), errors=())
        error = AdapterScanError(adapter="module.Adapter", error_type="RuntimeError", message="failed")

        with self.assertRaises(FrozenInstanceError):
            result.status = ScanStatus.FAILED

        with self.assertRaises(FrozenInstanceError):
            error.message = "changed"

    def test_result_collections_are_not_changed_through_external_references(self) -> None:
        resources = [_resource("service-1", "service")]
        adapter = StaticAdapter(resources)
        registry = Registry()
        registry.register(adapter)

        result = ScanEngine(registry).scan()
        resources.append(_resource("service-2", "service"))

        self.assertEqual([resource.id for resource in result.resources], ["service-1"])
        self.assertIsInstance(result.resources, tuple)
        self.assertIsInstance(result.errors, tuple)


if __name__ == "__main__":
    unittest.main()
