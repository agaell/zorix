from __future__ import annotations

import unittest

from zorix_core_model import Adapter, Resource
from zorix_registry import Registry
from zorix_resource_graph import ResourceRelation
from zorix_scan_engine import ScanEngine, ScanStatus
from zorix_topology_api import TopologyContext
from zorix_topology_engine import TopologyEngine, TopologyStatus


class PlainAdapter(Adapter):
    def discover(self) -> list[Resource]:
        return [
            Resource(
                id="service:api",
                type="service",
                name="api",
                state="active",
            ),
            Resource(
                id="database:main",
                type="database",
                name="main",
                state="active",
            ),
            Resource(
                id="server:node-1",
                type="server",
                name="node-1",
                state="active",
            ),
        ]


class ServiceTopologyAdapter(Adapter):
    def discover(self) -> list[Resource]:
        return []

    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        context.resource("service:api")
        context.resource("database:main")
        return [
            ResourceRelation(
                source_id="service:api",
                target_id="database:main",
                type="depends_on",
            )
        ]


class DatabaseTopologyAdapter(Adapter):
    def discover(self) -> list[Resource]:
        return []

    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        context.resource("server:node-1")
        context.resource("service:api")
        return [
            ResourceRelation(
                source_id="server:node-1",
                target_id="service:api",
                type="hosts",
            )
        ]


class TopologyEngineIntegrationTest(unittest.TestCase):
    def test_scan_resources_can_build_topology_graph(self) -> None:
        registry = Registry()
        registry.register_many(
            [
                PlainAdapter(),
                ServiceTopologyAdapter(),
                DatabaseTopologyAdapter(),
            ]
        )

        scan_result = ScanEngine(registry).scan()
        topology_result = TopologyEngine(registry).build(scan_result.resources)

        self.assertIs(scan_result.status, ScanStatus.SUCCESS)
        self.assertIs(topology_result.status, TopologyStatus.SUCCESS)
        self.assertEqual(topology_result.provider_count, 2)
        self.assertEqual(topology_result.successful_provider_count, 2)
        self.assertEqual(topology_result.errors, ())
        self.assertEqual(len(topology_result.graph), 3)
        self.assertEqual(len(topology_result.graph.relations()), 2)
        self.assertEqual(
            topology_result.graph.outgoing("service:api"),
            (ResourceRelation("service:api", "database:main", "depends_on"),),
        )
        self.assertEqual(
            topology_result.graph.incoming("service:api"),
            (ResourceRelation("server:node-1", "service:api", "hosts"),),
        )
        self.assertEqual(
            [resource.id for resource in topology_result.graph.neighbors("service:api")],
            ["database:main", "server:node-1"],
        )


if __name__ == "__main__":
    unittest.main()
