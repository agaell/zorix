from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from zorix_linux_adapter import LinuxAdapter, LinuxConfigurationError
from zorix_plugin_loader import PluginLoader
from zorix_registry import Registry
from zorix_scan_engine import ScanEngine, ScanStatus
from zorix_topology_api import TopologyProvider
from zorix_topology_engine import TopologyEngine, TopologyStatus


ROOT = Path(__file__).resolve().parents[3]


class FakeSshCommandRunner:
    def __init__(self, *outputs: str) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def run(self, target: str, arguments: tuple[str, ...]) -> str:
        self.calls.append((target, tuple(arguments)))
        if not self._outputs:
            raise AssertionError("unexpected SSH command")

        return self._outputs.pop(0)


class LinuxIntegrationTest(unittest.TestCase):
    def test_scan_resources_can_build_linux_topology_graph(self) -> None:
        runner = FakeSshCommandRunner(
            "tandem-server\n",
            "6.8.0\n",
            "x86_64\n",
            'ID=ubuntu\nPRETTY_NAME="Ubuntu 24.04 LTS"\nVERSION_ID="24.04"\n',
            (
                "nginx.service loaded active running Nginx\n"
                "tandem.service loaded active running Tandem\n"
                "postgresql.service loaded inactive dead PostgreSQL\n"
            ),
        )
        adapter = LinuxAdapter("tandem", runner)
        registry = Registry()
        registry.register(adapter)

        scan_result = ScanEngine(registry).scan()
        ssh_calls_after_scan = list(runner.calls)
        topology_result = TopologyEngine(registry).build(scan_result.resources)
        graph = topology_result.graph
        host_id = "linux:host:tandem"

        self.assertIs(scan_result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(scan_result.resources), 4)
        self.assertEqual(sum(1 for resource in scan_result.resources if resource.type == "host"), 1)
        self.assertEqual(sum(1 for resource in scan_result.resources if resource.type == "service"), 3)
        self.assertIs(topology_result.status, TopologyStatus.SUCCESS)
        self.assertEqual(topology_result.provider_count, 1)
        self.assertEqual(topology_result.successful_provider_count, 1)
        self.assertEqual(len(graph.relations()), 3)
        self.assertTrue(all(relation.type == "hosts" for relation in graph.relations()))
        self.assertEqual(
            [relation.target_id for relation in graph.outgoing(host_id)],
            [
                "linux:service:tandem:nginx.service",
                "linux:service:tandem:tandem.service",
                "linux:service:tandem:postgresql.service",
            ],
        )
        self.assertEqual(
            graph.incoming("linux:service:tandem:nginx.service"),
            (graph.relations()[0],),
        )
        self.assertEqual(
            [resource.id for resource in graph.neighbors(host_id)],
            [
                "linux:service:tandem:nginx.service",
                "linux:service:tandem:tandem.service",
                "linux:service:tandem:postgresql.service",
            ],
        )
        postgresql = graph.resource("linux:service:tandem:postgresql.service")
        self.assertEqual(postgresql.state, "inactive")
        self.assertEqual(runner.calls, ssh_calls_after_scan)


class LinuxPluginLoaderIntegrationTest(unittest.TestCase):
    def test_example_linux_plugin_is_loaded_from_environment_target(self) -> None:
        with patch.dict(os.environ, {"ZORIX_SSH_TARGET": "test-server"}, clear=False):
            adapters = PluginLoader().load(ROOT / "examples" / "plugins" / "linux")

        self.assertEqual(len(adapters), 1)
        self.assertIsInstance(adapters[0], LinuxAdapter)
        self.assertIsInstance(adapters[0], TopologyProvider)
        self.assertEqual(adapters[0].target, "test-server")

    def test_example_linux_plugin_requires_environment_target(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LinuxConfigurationError):
                PluginLoader().load(ROOT / "examples" / "plugins" / "linux")

    def test_example_plugin_does_not_reimplement_adapter(self) -> None:
        plugin_text = (
            ROOT / "examples" / "plugins" / "linux" / "linux_plugin.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("def discover", plugin_text)
        self.assertNotIn("def discover_relations", plugin_text)
        self.assertIn("Adapter = ConfiguredLinuxAdapter", plugin_text)


if __name__ == "__main__":
    unittest.main()
