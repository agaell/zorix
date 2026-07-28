from __future__ import annotations

import unittest

from zorix_core_model import Resource
from zorix_resource_graph import (
    ResourceGraphBuilder,
    ResourceRelation,
    UnknownResourceError,
)


class ResourceGraphTest(unittest.TestCase):
    def test_resources_returns_tuple(self) -> None:
        graph = _graph_with_resources("a")

        self.assertIsInstance(graph.resources(), tuple)

    def test_relations_returns_tuple(self) -> None:
        graph = _graph_with_relation(ResourceRelation("a", "b", "depends_on"))

        self.assertIsInstance(graph.relations(), tuple)

    def test_len_returns_resource_count(self) -> None:
        graph = _graph_with_resources("a", "b")

        self.assertEqual(len(graph), 2)

    def test_has_resource_for_existing_id(self) -> None:
        graph = _graph_with_resources("a")

        self.assertTrue(graph.has_resource("a"))

    def test_has_resource_for_unknown_id(self) -> None:
        graph = _graph_with_resources("a")

        self.assertFalse(graph.has_resource("missing"))

    def test_resource_returns_original_object(self) -> None:
        resource = _resource("a")
        builder = ResourceGraphBuilder()
        builder.add_resource(resource)

        graph = builder.build()

        self.assertIs(graph.resource("a"), resource)

    def test_resource_unknown_id_raises_error(self) -> None:
        graph = _graph_with_resources("a")

        with self.assertRaises(UnknownResourceError):
            graph.resource("missing")

    def test_resource_id_lookup_strips_user_input(self) -> None:
        graph = _graph_with_resources("a")

        self.assertTrue(graph.has_resource(" a "))
        self.assertEqual(graph.resource(" a ").id, "a")

    def test_outgoing_preserves_order(self) -> None:
        first = ResourceRelation("a", "b", "depends_on")
        second = ResourceRelation("a", "c", "uses")
        graph = _graph_with_relations(first, second)

        self.assertEqual(graph.outgoing("a"), (first, second))

    def test_incoming_preserves_order(self) -> None:
        first = ResourceRelation("b", "a", "depends_on")
        second = ResourceRelation("c", "a", "uses")
        graph = _graph_with_relations(first, second)

        self.assertEqual(graph.incoming("a"), (first, second))

    def test_outgoing_can_be_filtered_by_type(self) -> None:
        first = ResourceRelation("a", "b", "depends_on")
        second = ResourceRelation("a", "c", "uses")
        graph = _graph_with_relations(first, second)

        self.assertEqual(graph.outgoing("a", relation_type=" depends_on "), (first,))

    def test_incoming_can_be_filtered_by_type(self) -> None:
        first = ResourceRelation("b", "a", "depends_on")
        second = ResourceRelation("c", "a", "uses")
        graph = _graph_with_relations(first, second)

        self.assertEqual(graph.incoming("a", relation_type="uses"), (second,))

    def test_empty_result_is_tuple(self) -> None:
        graph = _graph_with_resources("a")

        self.assertEqual(graph.outgoing("a"), ())
        self.assertEqual(graph.incoming("a"), ())
        self.assertEqual(graph.neighbors("a"), ())

    def test_outgoing_unknown_resource_raises_error(self) -> None:
        graph = _graph_with_resources("a")

        with self.assertRaises(UnknownResourceError):
            graph.outgoing("missing")

    def test_incoming_unknown_resource_raises_error(self) -> None:
        graph = _graph_with_resources("a")

        with self.assertRaises(UnknownResourceError):
            graph.incoming("missing")

    def test_neighbors_include_both_directions(self) -> None:
        graph = _graph_with_relations(
            ResourceRelation("a", "b", "depends_on"),
            ResourceRelation("c", "a", "depends_on"),
        )

        self.assertEqual([resource.id for resource in graph.neighbors("a")], ["b", "c"])

    def test_neighbors_do_not_contain_duplicates(self) -> None:
        graph = _graph_with_relations(
            ResourceRelation("a", "b", "depends_on"),
            ResourceRelation("b", "a", "referenced_by"),
        )

        self.assertEqual([resource.id for resource in graph.neighbors("a")], ["b"])

    def test_neighbors_preserve_first_appearance_order(self) -> None:
        graph = _graph_with_relations(
            ResourceRelation("c", "a", "depends_on"),
            ResourceRelation("a", "b", "depends_on"),
        )

        self.assertEqual([resource.id for resource in graph.neighbors("a")], ["c", "b"])

    def test_neighbors_include_self_relation_once(self) -> None:
        graph = _graph_with_relations(ResourceRelation("a", "a", "references"))

        self.assertEqual([resource.id for resource in graph.neighbors("a")], ["a"])

    def test_neighbors_can_be_filtered_by_type(self) -> None:
        graph = _graph_with_relations(
            ResourceRelation("a", "b", "depends_on"),
            ResourceRelation("c", "a", "observes"),
        )

        self.assertEqual(
            [resource.id for resource in graph.neighbors("a", relation_type="depends_on")],
            ["b"],
        )

    def test_graph_does_not_change_after_builder_changes(self) -> None:
        builder = _builder_with_resources("a", "b")
        graph = builder.build()

        builder.add_relation(ResourceRelation("a", "b", "depends_on"))

        self.assertEqual(graph.relations(), ())


def _graph_with_resources(*resource_ids: str):
    return _builder_with_resources(*resource_ids).build()


def _graph_with_relation(relation: ResourceRelation):
    return _graph_with_relations(relation)


def _graph_with_relations(*relations: ResourceRelation):
    resource_ids: list[str] = []
    for relation in relations:
        if relation.source_id not in resource_ids:
            resource_ids.append(relation.source_id)
        if relation.target_id not in resource_ids:
            resource_ids.append(relation.target_id)

    builder = _builder_with_resources(*resource_ids)
    builder.add_relations(relations)
    return builder.build()


def _builder_with_resources(*resource_ids: str) -> ResourceGraphBuilder:
    builder = ResourceGraphBuilder()
    builder.add_resources([_resource(resource_id) for resource_id in resource_ids])
    return builder


def _resource(resource_id: str) -> Resource:
    return Resource(
        id=resource_id,
        type="service",
        name=resource_id,
        state="active",
    )


if __name__ == "__main__":
    unittest.main()
