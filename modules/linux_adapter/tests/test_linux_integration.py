from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from zorix_action_engine import ActionEngine
from zorix_action_model import ActionRequest
from zorix_linux_adapter import LinuxAdapter, LinuxConfigurationError
from zorix_health_engine import HealthEngine
from zorix_presentation import (
    ActionPlanConsoleRenderer,
    HealthConsoleRenderer,
    TopologyConsoleRenderer,
)
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
        self.input_texts: list[str | None] = []

    def run(
        self,
        target: str,
        arguments: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> str:
        self.calls.append((target, tuple(arguments)))
        self.input_texts.append(input_text)
        if not self._outputs:
            raise AssertionError("unexpected SSH command")

        return self._outputs.pop(0)


class LinuxIntegrationTest(unittest.TestCase):
    def test_scan_resources_can_build_linux_topology_graph(self) -> None:
        runner = FakeSshCommandRunner(
            _snapshot(
                hostname="tandem-server\n",
                kernel="6.8.0\n",
                architecture="x86_64\n",
                os_release='ID=ubuntu\nPRETTY_NAME="Ubuntu 24.04 LTS"\nVERSION_ID="24.04"\n',
                services=(
                    "nginx.service loaded active running Nginx\n"
                    "tandem.service loaded active running Tandem\n"
                    "postgresql.service loaded active running PostgreSQL\n"
                ),
                meminfo=(
                    "MemTotal:       8192000 kB\n"
                    "MemAvailable:   4096000 kB\n"
                    "SwapTotal:      2097152 kB\n"
                    "SwapFree:       1048576 kB\n"
                ),
                filesystems="/dev/vda1 ext4 50000000000 20000000000 30000000000 40% /\n",
                sockets=(
                    "tcp LISTEN 0 511 0.0.0.0:80 0.0.0.0:*\n"
                    "tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:*\n"
                    "tcp LISTEN 0 128 127.0.0.1:5432 0.0.0.0:*\n"
                ),
            )
        )
        adapter = LinuxAdapter("tandem", runner)
        registry = Registry()
        registry.register(adapter)

        scan_result = ScanEngine(registry).scan()
        ssh_calls_after_scan = list(runner.calls)
        topology_result = TopologyEngine(registry).build(scan_result.resources)
        rendered = TopologyConsoleRenderer().render(topology_result)
        graph = topology_result.graph
        host_id = "linux:host:tandem"

        self.assertIs(scan_result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(scan_result.resources), 9)
        self.assertEqual(runner.calls, [("tandem", ("sh", "-s"))])
        self.assertEqual(sum(1 for resource in scan_result.resources if resource.type == "host"), 1)
        self.assertEqual(sum(1 for resource in scan_result.resources if resource.type == "service"), 3)
        self.assertEqual(sum(1 for resource in scan_result.resources if resource.type == "memory"), 1)
        self.assertEqual(sum(1 for resource in scan_result.resources if resource.type == "filesystem"), 1)
        self.assertEqual(sum(1 for resource in scan_result.resources if resource.type == "socket"), 3)
        self.assertIs(topology_result.status, TopologyStatus.SUCCESS)
        self.assertEqual(topology_result.provider_count, 1)
        self.assertEqual(topology_result.successful_provider_count, 1)
        self.assertEqual(len(graph.relations()), 8)
        self.assertEqual(sum(1 for relation in graph.relations() if relation.type == "hosts"), 3)
        self.assertEqual(sum(1 for relation in graph.relations() if relation.type == "has_memory"), 1)
        self.assertEqual(sum(1 for relation in graph.relations() if relation.type == "mounts"), 1)
        self.assertEqual(sum(1 for relation in graph.relations() if relation.type == "listens_on"), 3)
        self.assertEqual(
            [relation.target_id for relation in graph.outgoing(host_id)],
            [
                "linux:service:tandem:nginx.service",
                "linux:service:tandem:tandem.service",
                "linux:service:tandem:postgresql.service",
                "linux:memory:tandem",
                "linux:filesystem:tandem:%2F",
                "linux:socket:tandem:tcp:0.0.0.0:80",
                "linux:socket:tandem:tcp:0.0.0.0:443",
                "linux:socket:tandem:tcp:127.0.0.1:5432",
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
                "linux:memory:tandem",
                "linux:filesystem:tandem:%2F",
                "linux:socket:tandem:tcp:0.0.0.0:80",
                "linux:socket:tandem:tcp:0.0.0.0:443",
                "linux:socket:tandem:tcp:127.0.0.1:5432",
            ],
        )
        postgresql = graph.resource("linux:service:tandem:postgresql.service")
        self.assertEqual(postgresql.state, "active")
        self.assertEqual(runner.calls, ssh_calls_after_scan)
        self.assertIn("--has_memory-->", rendered)
        self.assertIn("--mounts-->", rendered)
        self.assertIn("--listens_on-->", rendered)

    def test_scan_resources_can_evaluate_linux_health_without_second_ssh_call(self) -> None:
        runner = FakeSshCommandRunner(
            _snapshot(
                hostname="tandem-server\n",
                kernel="6.8.0\n",
                architecture="x86_64\n",
                os_release='ID=ubuntu\nPRETTY_NAME="Ubuntu 24.04 LTS"\nVERSION_ID="24.04"\n',
                services=(
                    "nginx.service loaded active running Nginx\n"
                    "tandem.service loaded failed failed Tandem\n"
                ),
                meminfo=(
                    "MemTotal:       8192000 kB\n"
                    "MemAvailable:   4096000 kB\n"
                ),
                filesystems="/dev/vda1 ext4 100 84 16 84% /\n",
                sockets="tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:*\n",
            )
        )
        adapter = LinuxAdapter("tandem", runner)
        registry = Registry()
        registry.register(adapter)

        scan_result = ScanEngine(registry).scan()
        ssh_calls_after_scan = list(runner.calls)
        health_result = HealthEngine(registry).evaluate(scan_result.resources)
        rendered = HealthConsoleRenderer().render(health_result)

        self.assertEqual(runner.calls, ssh_calls_after_scan)
        self.assertIn("Health evaluation: SUCCESS\n", rendered)
        self.assertIn("Health: CRITICAL\n", rendered)
        self.assertIn("Findings: 2\n", rendered)
        self.assertIn("Critical: 1\n", rendered)
        self.assertIn("Warnings: 1\n", rendered)
        self.assertIn(
            "- CRITICAL linux.service.failed: Service tandem.service is failed "
            "[linux:service:tandem:tandem.service]\n",
            rendered,
        )
        self.assertIn(
            "- WARNING linux.filesystem.usage_high: Filesystem / usage is 84% "
            "[linux:filesystem:tandem:%2F]\n",
            rendered,
        )

    def test_scan_resources_can_plan_linux_action_without_second_ssh_call(self) -> None:
        runner = FakeSshCommandRunner(
            _snapshot(
                hostname="tandem-server\n",
                kernel="6.8.0\n",
                architecture="x86_64\n",
                os_release='ID=ubuntu\nPRETTY_NAME="Ubuntu 24.04 LTS"\nVERSION_ID="24.04"\n',
                services="tandem.service loaded active running Tandem\n",
                meminfo="MemTotal:       8192000 kB\nMemAvailable:   4096000 kB\n",
                filesystems="/dev/vda1 ext4 100 20 80 20% /\n",
                sockets="tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:*\n",
            )
        )
        adapter = LinuxAdapter("tandem", runner)
        registry = Registry()
        registry.register(adapter)

        scan_result = ScanEngine(registry).scan()
        ssh_calls_after_scan = list(runner.calls)
        action_result = ActionEngine(registry).plan(
            scan_result.resources,
            ActionRequest(
                "service.restart",
                "linux:service:tandem:tandem.service",
            ),
        )
        rendered = ActionPlanConsoleRenderer().render(action_result)

        self.assertEqual(runner.calls, ssh_calls_after_scan)
        self.assertIn("Action planning: READY\n", rendered)
        self.assertIn("Dry run: yes\n", rendered)
        self.assertIn("Operation: linux.systemd.restart\n", rendered)
        self.assertIn("Risk: MEDIUM\n", rendered)
        self.assertIn("Confirmation required: yes\n", rendered)


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


def _snapshot(
    *,
    hostname: str,
    kernel: str,
    architecture: str,
    os_release: str,
    services: str,
    meminfo: str,
    filesystems: str,
    sockets: str,
) -> str:
    return "".join(
        (
            _section("hostname", hostname),
            _section("kernel", kernel),
            _section("architecture", architecture),
            _section("os_release", os_release),
            _section("services", services),
            _section("meminfo", meminfo),
            _section("filesystems", filesystems),
            _section("sockets", sockets),
        )
    )


def _section(name: str, content: str) -> str:
    return (
        f"__ZORIX_SNAPSHOT_V1_BEGIN__:{name}\n"
        f"{content}"
        f"\n__ZORIX_SNAPSHOT_V1_END__:{name}\n"
    )


if __name__ == "__main__":
    unittest.main()
