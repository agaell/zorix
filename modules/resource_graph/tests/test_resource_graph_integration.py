from __future__ import annotations

import unittest

from zorix_mock_adapter import MockAdapter
from zorix_registry import Registry
from zorix_resource_graph import ResourceGraphBuilder, ResourceRelation
from zorix_scan_engine import ScanEngine, ScanStatus


class ResourceGraphIntegrationTest(unittest.TestCase):
    def test_scan_result_resources_can_build_resource_graph(self) -> None:
        registry = Registry()
        registry.register(MockAdapter())

        result = ScanEngine(registry).scan()
        builder = ResourceGraphBuilder()
        builder.add_resources(result.resources)
        service_to_container = ResourceRelation(
            source_id="mock-service-1",
            target_id="mock-container-1",
            type="runs_on",
        )
        user_to_service = ResourceRelation(
            source_id="mock-user-1",
            target_id="mock-service-1",
            type="owns",
        )
        builder.add_relations([service_to_container, user_to_service])

        graph = builder.build()

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(graph), 5)
        self.assertEqual(len(graph.relations()), 2)
        self.assertEqual(graph.outgoing("mock-service-1"), (service_to_container,))
        self.assertEqual(graph.incoming("mock-service-1"), (user_to_service,))
        self.assertEqual(
            [resource.id for resource in graph.neighbors("mock-service-1")],
            ["mock-container-1", "mock-user-1"],
        )


if __name__ == "__main__":
    unittest.main()
