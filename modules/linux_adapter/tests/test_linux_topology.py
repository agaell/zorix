from __future__ import annotations

import copy
import unittest

from zorix_core_model import Adapter, Resource
from zorix_linux_adapter import LinuxAdapter
from zorix_topology_api import TopologyContext, TopologyProvider


class FailingRunner:
    def run(self, target: str, arguments: tuple[str, ...]) -> str:
        raise AssertionError("SSH must not be called")


class LinuxTopologyTest(unittest.TestCase):
    def test_linux_adapter_is_adapter_and_topology_provider(self) -> None:
        adapter = LinuxAdapter("tandem", FailingRunner())

        self.assertIsInstance(adapter, Adapter)
        self.assertIsInstance(adapter, TopologyProvider)

    def test_empty_context_and_context_without_host_return_empty(self) -> None:
        adapter = LinuxAdapter("tandem", FailingRunner())

        self.assertEqual(adapter.discover_relations(TopologyContext([])), [])
        self.assertEqual(
            adapter.discover_relations(
                TopologyContext([_service("nginx.service")])
            ),
            [],
        )

    def test_host_without_services_returns_empty(self) -> None:
        adapter = LinuxAdapter("tandem", FailingRunner())

        relations = adapter.discover_relations(TopologyContext([_host()]))

        self.assertEqual(relations, [])

    def test_host_to_service_relation_mapping_and_order(self) -> None:
        adapter = LinuxAdapter("tandem", FailingRunner())
        context = TopologyContext(
            [
                _host(),
                _service("nginx.service"),
                _service("postgresql.service"),
            ]
        )

        relations = adapter.discover_relations(context)

        self.assertEqual(len(relations), 2)
        self.assertEqual(relations[0].source_id, "linux:host:tandem")
        self.assertEqual(relations[0].target_id, "linux:service:tandem:nginx.service")
        self.assertEqual(relations[0].type, "hosts")
        self.assertEqual(relations[0].metadata, {})
        self.assertEqual(
            [relation.target_id for relation in relations],
            [
                "linux:service:tandem:nginx.service",
                "linux:service:tandem:postgresql.service",
            ],
        )

    def test_foreign_resources_are_ignored(self) -> None:
        adapter = LinuxAdapter("tandem", FailingRunner())
        context = TopologyContext(
            [
                _host(),
                _service("nginx.service", target="other"),
                Resource("docker:service:nginx.service", "service", "nginx", "active"),
                Resource(
                    "linux:service:tandem:no-host-id.service",
                    "service",
                    "no-host-id.service",
                    "active",
                ),
                Resource(
                    "linux:service:tandem:wrong-host.service",
                    "service",
                    "wrong-host.service",
                    "active",
                    metadata={"host_id": "linux:host:other"},
                ),
            ]
        )

        relations = adapter.discover_relations(context)

        self.assertEqual(relations, [])

    def test_context_and_resources_are_not_mutated_and_repeated_call_is_identical(self) -> None:
        adapter = LinuxAdapter("tandem", FailingRunner())
        resources = [_host(), _service("nginx.service")]
        before = copy.deepcopy(resources)
        context = TopologyContext(resources)

        first = adapter.discover_relations(context)
        second = adapter.discover_relations(context)

        self.assertEqual(first, second)
        self.assertEqual(resources, before)


def _host(target: str = "tandem") -> Resource:
    return Resource(
        id=f"linux:host:{target}",
        type="host",
        name=f"{target}-server",
        state="reachable",
    )


def _service(unit: str, target: str = "tandem") -> Resource:
    return Resource(
        id=f"linux:service:{target}:{unit}",
        type="service",
        name=unit,
        state="active",
        metadata={"host_id": f"linux:host:{target}", "unit": unit},
    )


if __name__ == "__main__":
    unittest.main()
