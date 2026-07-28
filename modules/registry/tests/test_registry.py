from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "modules" / "core_model" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "registry" / "src"))

from zorix_core_model import Adapter, Resource
from zorix_registry import DuplicateAdapterError, Registry


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
    def discover(self) -> list[Resource]:
        raise RuntimeError("discovery failed")


class RegistryTest(unittest.TestCase):
    def test_registers_adapter(self) -> None:
        registry = Registry()
        adapter = StaticAdapter([_resource("service-1", "service")])

        registry.register(adapter)

        self.assertEqual(registry.adapters(), (adapter,))

    def test_registers_many_adapters(self) -> None:
        registry = Registry()
        first_adapter = StaticAdapter([_resource("service-1", "service")])
        second_adapter = AnotherStaticAdapter([_resource("user-1", "user")])

        registry.register_many([first_adapter, second_adapter])

        self.assertEqual(registry.adapters(), (first_adapter, second_adapter))

    def test_rejects_duplicate_adapter_type(self) -> None:
        registry = Registry()
        registry.register(StaticAdapter([_resource("service-1", "service")]))

        with self.assertRaises(DuplicateAdapterError):
            registry.register(StaticAdapter([_resource("service-2", "service")]))

    def test_register_duplicate_error_contains_full_class_name(self) -> None:
        registry = Registry()
        registry.register(StaticAdapter([_resource("service-1", "service")]))
        expected_name = f"{StaticAdapter.__module__}.{StaticAdapter.__qualname__}"

        with self.assertRaisesRegex(DuplicateAdapterError, expected_name):
            registry.register(StaticAdapter([_resource("service-2", "service")]))

    def test_register_many_is_atomic_when_adapter_is_already_registered(self) -> None:
        registry = Registry()
        registered_adapter = StaticAdapter([_resource("service-1", "service")])
        new_adapter = AnotherStaticAdapter([_resource("user-1", "user")])
        registry.register(registered_adapter)

        with self.assertRaises(DuplicateAdapterError):
            registry.register_many([new_adapter, StaticAdapter([_resource("service-2", "service")])])

        self.assertEqual(registry.adapters(), (registered_adapter,))

    def test_register_many_is_atomic_with_duplicate_input_types(self) -> None:
        registry = Registry()
        first_adapter = StaticAdapter([_resource("service-1", "service")])
        second_adapter = StaticAdapter([_resource("service-2", "service")])

        with self.assertRaises(DuplicateAdapterError):
            registry.register_many([first_adapter, second_adapter])

        self.assertEqual(registry.adapters(), ())

    def test_register_many_accepts_generator(self) -> None:
        registry = Registry()
        first_adapter = StaticAdapter([_resource("service-1", "service")])
        second_adapter = AnotherStaticAdapter([_resource("user-1", "user")])

        registry.register_many(adapter for adapter in [first_adapter, second_adapter])

        self.assertEqual(registry.adapters(), (first_adapter, second_adapter))

    def test_adapters_returns_tuple(self) -> None:
        registry = Registry()
        adapter = StaticAdapter([_resource("service-1", "service")])

        registry.register(adapter)

        self.assertIsInstance(registry.adapters(), tuple)

    def test_adapters_result_cannot_mutate_registry_state(self) -> None:
        registry = Registry()
        adapter = StaticAdapter([_resource("service-1", "service")])
        extra_adapter = AnotherStaticAdapter([_resource("user-1", "user")])
        registry.register(adapter)

        adapters = registry.adapters()
        adapters += (extra_adapter,)

        self.assertEqual(registry.adapters(), (adapter,))

    def test_scan_returns_resources_from_all_adapters(self) -> None:
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

        resources = registry.scan()

        self.assertEqual([resource.id for resource in resources], ["service-1", "container-1", "user-1"])

    def test_clear_removes_registered_adapters(self) -> None:
        registry = Registry()
        registry.register(StaticAdapter([_resource("service-1", "service")]))

        registry.clear()

        self.assertEqual(registry.adapters(), ())

    def test_scan_without_adapters_returns_empty_list(self) -> None:
        registry = Registry()

        self.assertEqual(registry.scan(), [])

    def test_scan_propagates_discover_exception(self) -> None:
        registry = Registry()
        registry.register(FailingAdapter())

        with self.assertRaisesRegex(RuntimeError, "discovery failed"):
            registry.scan()


if __name__ == "__main__":
    unittest.main()
