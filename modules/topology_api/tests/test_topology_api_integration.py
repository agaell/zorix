from __future__ import annotations

import unittest

from zorix_core_model import Adapter, Resource
from zorix_registry import Registry
from zorix_resource_graph import ResourceGraphBuilder, ResourceRelation
from zorix_scan_engine import ScanEngine, ScanStatus
from zorix_topology_api import TopologyContext, TopologyProvider


class TopologyAwareAdapter(Adapter):
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
        ]

    def discover_relations(
        self,
        context: TopologyContext,
    ) -> list[ResourceRelation]:
        context.resource("service:api")
        context.resource("database:main")
        return [
            ResourceRelation(
                source_id="service:api",
                target_id="database:main",
                type="depends_on",
            )
        ]


class TopologyApiIntegrationTest(unittest.TestCase):
    def test_topology_provider_relations_build_resource_graph(self) -> None:
        adapter = TopologyAwareAdapter()
        registry = Registry()
        registry.register(adapter)

        result = ScanEngine(registry).scan()
        context = TopologyContext(result.resources)
        self.assertIsInstance(adapter, TopologyProvider)
        relations = adapter.discover_relations(context)
        builder = ResourceGraphBuilder()
        builder.add_resources(result.resources)
        builder.add_relations(relations)

        graph = builder.build()

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(graph.outgoing("service:api"), tuple(relations))
        self.assertEqual(graph.incoming("database:main"), tuple(relations))
        self.assertEqual(
            [resource.id for resource in graph.neighbors("service:api")],
            ["database:main"],
        )
        self.assertEqual(relations[0].type, "depends_on")


if __name__ == "__main__":
    unittest.main()
