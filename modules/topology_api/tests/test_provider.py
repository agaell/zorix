from __future__ import annotations

import unittest

from zorix_core_model import Adapter, Resource
from zorix_mock_adapter import MockAdapter
from zorix_resource_graph import ResourceRelation
from zorix_topology_api import TopologyContext, TopologyProvider


class ExampleTopologyProvider:
    def __init__(self) -> None:
        self.received_context: TopologyContext | None = None

    def discover_relations(
        self,
        context: TopologyContext,
    ) -> list[ResourceRelation]:
        self.received_context = context
        return []


class ResourceAndTopologyAdapter(Adapter):
    def discover(self) -> list[Resource]:
        return [_resource("service:api", "service"), _resource("database:main", "database")]

    def discover_relations(
        self,
        context: TopologyContext,
    ) -> list[ResourceRelation]:
        context.resource("service:api")
        return [
            ResourceRelation("service:api", "database:main", "depends_on"),
            ResourceRelation("database:main", "service:api", "used_by"),
        ]


class PlainObject:
    pass


class TopologyProviderTest(unittest.TestCase):
    def test_provider_is_runtime_checkable(self) -> None:
        self.assertIsInstance(ExampleTopologyProvider(), TopologyProvider)

    def test_object_without_discover_relations_is_not_provider(self) -> None:
        self.assertNotIsInstance(PlainObject(), TopologyProvider)

    def test_mock_adapter_is_not_provider(self) -> None:
        self.assertNotIsInstance(MockAdapter(), TopologyProvider)

    def test_object_can_be_adapter_and_topology_provider(self) -> None:
        adapter = ResourceAndTopologyAdapter()

        self.assertIsInstance(adapter, Adapter)
        self.assertIsInstance(adapter, TopologyProvider)

    def test_empty_relations_list_is_allowed(self) -> None:
        context = TopologyContext([_resource("service:api", "service")])

        relations = ExampleTopologyProvider().discover_relations(context)

        self.assertEqual(relations, [])

    def test_provider_receives_same_topology_context(self) -> None:
        provider = ExampleTopologyProvider()
        context = TopologyContext([_resource("service:api", "service")])

        provider.discover_relations(context)

        self.assertIs(provider.received_context, context)

    def test_provider_can_find_resource_through_context(self) -> None:
        adapter = ResourceAndTopologyAdapter()
        resources = adapter.discover()
        context = TopologyContext(resources)

        relations = adapter.discover_relations(context)

        self.assertEqual(len(relations), 2)

    def test_provider_can_return_resource_relation(self) -> None:
        adapter = ResourceAndTopologyAdapter()
        context = TopologyContext(adapter.discover())

        relations = adapter.discover_relations(context)

        self.assertIsInstance(relations[0], ResourceRelation)

    def test_returned_relation_order_is_preserved(self) -> None:
        adapter = ResourceAndTopologyAdapter()
        context = TopologyContext(adapter.discover())

        relations = adapter.discover_relations(context)

        self.assertEqual(
            [relation.type for relation in relations],
            ["depends_on", "used_by"],
        )

    def test_topology_provider_does_not_inherit_adapter(self) -> None:
        self.assertNotIn(Adapter, TopologyProvider.__mro__)


def _resource(resource_id: str, resource_type: str) -> Resource:
    return Resource(
        id=resource_id,
        type=resource_type,
        name=resource_id,
        state="active",
    )


if __name__ == "__main__":
    unittest.main()
