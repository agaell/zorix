from __future__ import annotations

import copy
import unittest

from zorix_core_model import Adapter, Resource
from zorix_linux_adapter import LinuxAdapter
from zorix_topology_api import TopologyContext, TopologyProvider


class FailingRunner:
    def run(
        self,
        target: str,
        arguments: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> str:
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

    def test_host_relation_mapping_and_order(self) -> None:
        adapter = LinuxAdapter("tandem", FailingRunner())
        context = TopologyContext(
            [
                _host(),
                _service("nginx.service"),
                _service("postgresql.service"),
                _memory(),
                _filesystem("/"),
                _socket("tcp", "0.0.0.0", 443),
            ]
        )

        relations = adapter.discover_relations(context)

        self.assertEqual(len(relations), 5)
        self.assertEqual(relations[0].source_id, "linux:host:tandem")
        self.assertEqual(relations[0].target_id, "linux:service:tandem:nginx.service")
        self.assertEqual(relations[0].type, "hosts")
        self.assertEqual(relations[0].metadata, {})
        self.assertEqual(relations[2].target_id, "linux:memory:tandem")
        self.assertEqual(relations[2].type, "has_memory")
        self.assertEqual(relations[3].type, "mounts")
        self.assertEqual(relations[4].type, "listens_on")
        self.assertEqual(
            [(relation.type, relation.target_id) for relation in relations],
            [
                ("hosts", "linux:service:tandem:nginx.service"),
                ("hosts", "linux:service:tandem:postgresql.service"),
                ("has_memory", "linux:memory:tandem"),
                ("mounts", "linux:filesystem:tandem:%2F"),
                ("listens_on", "linux:socket:tandem:tcp:0.0.0.0:443"),
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
                _memory(target="other"),
                Resource(
                    "linux:memory:tandem",
                    "memory",
                    "System memory",
                    "present",
                    metadata={"host_id": "linux:host:other"},
                ),
                _filesystem("/", target="other"),
                Resource(
                    "linux:filesystem:tandem:%2Fwrong",
                    "filesystem",
                    "/wrong",
                    "mounted",
                    metadata={"host_id": "linux:host:other"},
                ),
                _socket("tcp", "0.0.0.0", 443, target="other"),
                Resource(
                    "linux:socket:tandem:tcp:0.0.0.0:8080",
                    "socket",
                    "tcp://0.0.0.0:8080",
                    "listening",
                    metadata={"host_id": "linux:host:other"},
                ),
            ]
        )

        relations = adapter.discover_relations(context)

        self.assertEqual(relations, [])

    def test_context_and_resources_are_not_mutated_and_repeated_call_is_identical(self) -> None:
        adapter = LinuxAdapter("tandem", FailingRunner())
        resources = [_host(), _service("nginx.service"), _memory(), _filesystem("/"), _socket("tcp", "0.0.0.0", 443)]
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


def _memory(target: str = "tandem") -> Resource:
    return Resource(
        id=f"linux:memory:{target}",
        type="memory",
        name="System memory",
        state="present",
        metadata={"host_id": f"linux:host:{target}"},
    )


def _filesystem(mountpoint: str, target: str = "tandem") -> Resource:
    encoded = "%2F" if mountpoint == "/" else mountpoint
    return Resource(
        id=f"linux:filesystem:{target}:{encoded}",
        type="filesystem",
        name=mountpoint,
        state="mounted",
        metadata={"host_id": f"linux:host:{target}", "mountpoint": mountpoint},
    )


def _socket(protocol: str, address: str, port: int, target: str = "tandem") -> Resource:
    return Resource(
        id=f"linux:socket:{target}:{protocol}:{address}:{port}",
        type="socket",
        name=f"{protocol}://{address}:{port}",
        state="listening",
        metadata={"host_id": f"linux:host:{target}", "protocol": protocol},
    )


if __name__ == "__main__":
    unittest.main()
