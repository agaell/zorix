from __future__ import annotations

import unittest

from zorix_core_model import Resource
from zorix_resource_graph import (
    DuplicateRelationError,
    DuplicateResourceError,
    InvalidRelationError,
    ResourceGraph,
    ResourceGraphBuilder,
    ResourceRelation,
)


class ResourceGraphBuilderTest(unittest.TestCase):
    def test_adds_one_resource(self) -> None:
        builder = ResourceGraphBuilder()
        resource = _resource("service:api")

        builder.add_resource(resource)
        graph = builder.build()

        self.assertEqual(graph.resources(), (resource,))

    def test_adds_multiple_resources(self) -> None:
        builder = ResourceGraphBuilder()
        resources = [_resource("service:api"), _resource("database:main")]

        builder.add_resources(resources)

        self.assertEqual(builder.build().resources(), tuple(resources))

    def test_resource_order_is_preserved(self) -> None:
        builder = ResourceGraphBuilder()
        resources = [_resource("a"), _resource("b"), _resource("c")]

        builder.add_resources(resources)

        self.assertEqual(builder.build().resources(), tuple(resources))

    def test_duplicate_resource_is_rejected(self) -> None:
        builder = ResourceGraphBuilder()
        builder.add_resource(_resource("service:api"))

        with self.assertRaises(DuplicateResourceError):
            builder.add_resource(_resource("service:api"))

    def test_duplicate_resource_inside_batch_is_rejected(self) -> None:
        builder = ResourceGraphBuilder()

        with self.assertRaises(DuplicateResourceError):
            builder.add_resources([_resource("service:api"), _resource("service:api")])

    def test_add_resources_is_atomic(self) -> None:
        builder = ResourceGraphBuilder()
        existing = _resource("existing")
        builder.add_resource(existing)

        with self.assertRaises(DuplicateResourceError):
            builder.add_resources([_resource("new"), _resource("existing")])

        self.assertEqual(builder.build().resources(), (existing,))

    def test_invalid_resource_id_rejects_entire_batch(self) -> None:
        builder = ResourceGraphBuilder()

        with self.assertRaises(ValueError):
            builder.add_resources([_resource("valid"), _resource(" invalid ")])

        self.assertEqual(builder.build().resources(), ())

    def test_adds_one_relation(self) -> None:
        builder = _builder_with_resources("a", "b")
        relation = ResourceRelation("a", "b", "depends_on")

        builder.add_relation(relation)

        self.assertEqual(builder.build().relations(), (relation,))

    def test_adds_multiple_relations(self) -> None:
        builder = _builder_with_resources("a", "b", "c")
        relations = [
            ResourceRelation("a", "b", "depends_on"),
            ResourceRelation("b", "c", "uses"),
        ]

        builder.add_relations(relations)

        self.assertEqual(builder.build().relations(), tuple(relations))

    def test_relation_order_is_preserved(self) -> None:
        builder = _builder_with_resources("a", "b", "c")
        first = ResourceRelation("a", "b", "depends_on")
        second = ResourceRelation("c", "a", "observes")

        builder.add_relations([first, second])

        self.assertEqual(builder.build().relations(), (first, second))

    def test_duplicate_relation_is_rejected(self) -> None:
        builder = _builder_with_resources("a", "b")
        relation = ResourceRelation("a", "b", "depends_on", {"reason": "first"})
        builder.add_relation(relation)

        with self.assertRaises(DuplicateRelationError):
            builder.add_relation(ResourceRelation("a", "b", "depends_on", {"reason": "second"}))

    def test_duplicate_relation_inside_batch_is_rejected(self) -> None:
        builder = _builder_with_resources("a", "b")

        with self.assertRaises(DuplicateRelationError):
            builder.add_relations(
                [
                    ResourceRelation("a", "b", "depends_on"),
                    ResourceRelation("a", "b", "depends_on", {"reason": "same identity"}),
                ]
            )

    def test_add_relations_is_atomic(self) -> None:
        builder = _builder_with_resources("a", "b", "c")
        existing = ResourceRelation("a", "b", "depends_on")
        builder.add_relation(existing)

        with self.assertRaises(DuplicateRelationError):
            builder.add_relations(
                [
                    ResourceRelation("b", "c", "uses"),
                    ResourceRelation("a", "b", "depends_on"),
                ]
            )

        self.assertEqual(builder.build().relations(), (existing,))

    def test_relation_with_unknown_source_is_rejected(self) -> None:
        builder = _builder_with_resources("b")

        with self.assertRaises(InvalidRelationError):
            builder.add_relation(ResourceRelation("a", "b", "depends_on"))

    def test_relation_with_unknown_target_is_rejected(self) -> None:
        builder = _builder_with_resources("a")

        with self.assertRaises(InvalidRelationError):
            builder.add_relation(ResourceRelation("a", "b", "depends_on"))

    def test_missing_resource_ids_order_is_source_then_target(self) -> None:
        builder = ResourceGraphBuilder()
        relation = ResourceRelation("source", "target", "depends_on")

        with self.assertRaises(InvalidRelationError) as context:
            builder.add_relation(relation)

        self.assertEqual(context.exception.missing_resource_ids, ("source", "target"))

    def test_build_creates_resource_graph(self) -> None:
        graph = _builder_with_resources("a").build()

        self.assertIsInstance(graph, ResourceGraph)

    def test_builder_changes_after_build_do_not_change_graph(self) -> None:
        builder = _builder_with_resources("a", "b")
        graph = builder.build()

        builder.add_resource(_resource("c"))
        builder.add_relation(ResourceRelation("a", "b", "depends_on"))

        self.assertEqual(len(graph), 2)
        self.assertEqual(graph.relations(), ())

    def test_clear_empties_builder(self) -> None:
        builder = _builder_with_resources("a", "b")
        builder.add_relation(ResourceRelation("a", "b", "depends_on"))

        builder.clear()

        self.assertEqual(builder.build().resources(), ())
        self.assertEqual(builder.build().relations(), ())

    def test_clear_does_not_change_existing_graph(self) -> None:
        builder = _builder_with_resources("a", "b")
        relation = ResourceRelation("a", "b", "depends_on")
        builder.add_relation(relation)
        graph = builder.build()

        builder.clear()

        self.assertEqual(len(graph), 2)
        self.assertEqual(graph.relations(), (relation,))

    def test_repeated_build_is_allowed(self) -> None:
        builder = _builder_with_resources("a")

        first = builder.build()
        second = builder.build()

        self.assertEqual(first.resources(), second.resources())


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
