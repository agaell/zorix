from __future__ import annotations

from collections import Counter
import unittest
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[3]

from zorix_scan_engine import ScanStatus
from zorix_runtime import ZorixRuntime
from zorix_topology_engine import TopologyStatus


class RuntimeIntegrationTest(unittest.TestCase):
    def test_plugin_loader_registry_scan_engine_chain(self) -> None:
        runtime = ZorixRuntime()

        adapters = runtime.load_plugins(ROOT / "modules" / "mock_adapter")
        result = runtime.scan()
        resource_types = Counter(resource.type for resource in result.resources)

        self.assertEqual(len(adapters), 1)
        self.assertEqual(runtime.adapters(), adapters)
        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(result.resources), 5)
        self.assertEqual(resource_types["service"], 2)
        self.assertEqual(resource_types["container"], 1)
        self.assertEqual(resource_types["user"], 2)

    def test_topology_uses_registered_adapter_without_second_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_root = Path(directory)
            _write_plugin(plugin_root, "topology_adapter", _topology_adapter_source())
            runtime = ZorixRuntime()

            loaded_adapters = runtime.load_plugins(plugin_root)
            scan_result = runtime.scan()
            topology_result = runtime.build_topology(scan_result.resources)

        adapter = loaded_adapters[0]
        self.assertEqual(runtime.adapters(), loaded_adapters)
        self.assertIs(runtime.adapters()[0], adapter)
        self.assertIs(scan_result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(scan_result.resources), 2)
        self.assertEqual(adapter.discover_calls, 1)
        self.assertEqual(adapter.discover_relations_calls, 1)
        self.assertIs(topology_result.status, TopologyStatus.SUCCESS)
        self.assertEqual(topology_result.provider_count, 1)
        self.assertEqual(topology_result.successful_provider_count, 1)
        self.assertEqual(topology_result.errors, ())
        self.assertEqual(len(topology_result.graph.resources()), 2)
        self.assertEqual(len(topology_result.graph.relations()), 1)

        relation = topology_result.graph.relations()[0]
        self.assertEqual(relation.type, "depends_on")
        self.assertEqual(topology_result.graph.outgoing("service:api"), (relation,))
        self.assertEqual(topology_result.graph.incoming("database:main"), (relation,))
        self.assertEqual(
            tuple(resource.id for resource in topology_result.graph.neighbors("service:api")),
            ("database:main",),
        )

    def test_clear_removes_topology_providers_but_preserves_input_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_root = Path(directory)
            _write_plugin(plugin_root, "topology_adapter", _topology_adapter_source())
            runtime = ZorixRuntime()

            runtime.load_plugins(plugin_root)
            scan_result = runtime.scan()
            runtime.clear()
            topology_result = runtime.build_topology(scan_result.resources)

        self.assertEqual(runtime.adapters(), ())
        self.assertIs(topology_result.status, TopologyStatus.SUCCESS)
        self.assertEqual(topology_result.provider_count, 0)
        self.assertEqual(topology_result.successful_provider_count, 0)
        self.assertEqual(len(topology_result.graph.resources()), 2)
        self.assertEqual(topology_result.graph.relations(), ())

    def test_topology_continue_on_error_preserves_successful_provider_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_root = Path(directory)
            _write_plugin(plugin_root, "provider_a", _provider_a_source())
            _write_plugin(plugin_root, "provider_b", _provider_b_source())
            runtime = ZorixRuntime()

            runtime.load_plugins(plugin_root)
            scan_result = runtime.scan()
            topology_result = runtime.build_topology(
                scan_result.resources,
                continue_on_error=True,
            )

            with self.assertRaises(RuntimeError) as context:
                runtime.build_topology(scan_result.resources)

        self.assertEqual(str(context.exception), "provider B failed")
        self.assertIs(topology_result.status, TopologyStatus.PARTIAL)
        self.assertEqual(topology_result.provider_count, 2)
        self.assertEqual(topology_result.successful_provider_count, 1)
        self.assertEqual(topology_result.failed_provider_count, 1)
        self.assertEqual(len(topology_result.errors), 1)
        self.assertEqual(topology_result.errors[0].error_type, "RuntimeError")
        self.assertEqual(len(topology_result.graph.relations()), 1)
        self.assertEqual(topology_result.graph.relations()[0].type, "depends_on")


def _write_plugin(plugin_root: Path, package_name: str, source: str) -> None:
    package_dir = plugin_root / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(source, encoding="utf-8")


def _topology_adapter_source() -> str:
    return """\
from zorix_core_model import Adapter as CoreAdapter, Resource
from zorix_resource_graph import ResourceRelation


class Adapter(CoreAdapter):
    def __init__(self):
        self.discover_calls = 0
        self.discover_relations_calls = 0

    def discover(self):
        self.discover_calls += 1
        return [
            Resource("service:api", "service", "api", "running"),
            Resource("database:main", "database", "main", "running"),
        ]

    def discover_relations(self, context):
        self.discover_relations_calls += 1
        return [
            ResourceRelation(
                source_id="service:api",
                target_id="database:main",
                type="depends_on",
            )
        ]
"""


def _provider_a_source() -> str:
    return """\
from zorix_core_model import Adapter as CoreAdapter, Resource
from zorix_resource_graph import ResourceRelation


class Adapter(CoreAdapter):
    def discover(self):
        return [
            Resource("service:api", "service", "api", "running"),
            Resource("database:main", "database", "main", "running"),
        ]

    def discover_relations(self, context):
        return [
            ResourceRelation(
                source_id="service:api",
                target_id="database:main",
                type="depends_on",
            )
        ]
"""


def _provider_b_source() -> str:
    return """\
from zorix_core_model import Adapter as CoreAdapter, Resource


class Adapter(CoreAdapter):
    def discover(self):
        return [
            Resource("service:worker", "service", "worker", "running"),
        ]

    def discover_relations(self, context):
        raise RuntimeError("provider B failed")
"""


if __name__ == "__main__":
    unittest.main()
