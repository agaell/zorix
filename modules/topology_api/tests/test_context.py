from __future__ import annotations

import unittest

from zorix_core_model import Resource
from zorix_resource_graph import DuplicateResourceError, UnknownResourceError
from zorix_topology_api import TopologyContext


class TopologyContextTest(unittest.TestCase):
    def test_creates_context_with_one_resource(self) -> None:
        resource = _resource("service:api", "service")

        context = TopologyContext([resource])

        self.assertEqual(context.resources(), (resource,))

    def test_creates_context_with_multiple_resources(self) -> None:
        resources = [
            _resource("service:api", "service"),
            _resource("database:main", "database"),
        ]

        context = TopologyContext(resources)

        self.assertEqual(context.resources(), tuple(resources))

    def test_creates_context_from_generator(self) -> None:
        context = TopologyContext(
            _resource(resource_id, "service")
            for resource_id in ("service:api", "service:worker")
        )

        self.assertEqual([resource.id for resource in context.resources()], ["service:api", "service:worker"])

    def test_resource_order_is_preserved(self) -> None:
        resources = [
            _resource("a", "service"),
            _resource("b", "database"),
            _resource("c", "service"),
        ]

        context = TopologyContext(resources)

        self.assertEqual(context.resources(), tuple(resources))

    def test_resources_returns_tuple(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        self.assertIsInstance(context.resources(), tuple)

    def test_original_list_can_change_without_changing_context(self) -> None:
        resources = [_resource("a", "service")]
        context = TopologyContext(resources)

        resources.append(_resource("b", "service"))

        self.assertEqual([resource.id for resource in context.resources()], ["a"])

    def test_context_returns_original_resource_objects(self) -> None:
        resource = _resource("a", "service")
        context = TopologyContext([resource])

        self.assertIs(context.resource("a"), resource)

    def test_duplicate_resource_id_raises_duplicate_resource_error(self) -> None:
        with self.assertRaises(DuplicateResourceError):
            TopologyContext([_resource("a", "service"), _resource("a", "database")])

    def test_invalid_resource_uses_builder_error(self) -> None:
        with self.assertRaises(ValueError):
            TopologyContext([_resource(" invalid ", "service")])

    def test_has_resource_for_existing_id(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        self.assertTrue(context.has_resource("a"))

    def test_has_resource_for_unknown_id(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        self.assertFalse(context.has_resource("missing"))

    def test_has_resource_strips_external_whitespace(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        self.assertTrue(context.has_resource(" a "))

    def test_has_resource_with_empty_string_returns_false(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        self.assertFalse(context.has_resource(" "))

    def test_has_resource_with_non_string_returns_false(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        self.assertFalse(context.has_resource(1))

    def test_resource_returns_existing_resource(self) -> None:
        resource = _resource("a", "service")
        context = TopologyContext([resource])

        self.assertIs(context.resource("a"), resource)

    def test_resource_strips_external_whitespace(self) -> None:
        resource = _resource("a", "service")
        context = TopologyContext([resource])

        self.assertIs(context.resource(" a "), resource)

    def test_resource_unknown_id_raises_unknown_resource_error(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        with self.assertRaises(UnknownResourceError):
            context.resource("missing")

    def test_resources_by_type_returns_matching_resources(self) -> None:
        service = _resource("service:api", "service")
        database = _resource("database:main", "database")
        context = TopologyContext([service, database])

        self.assertEqual(context.resources_by_type("service"), (service,))

    def test_resources_by_type_preserves_order(self) -> None:
        first = _resource("service:api", "service")
        database = _resource("database:main", "database")
        second = _resource("service:worker", "service")
        context = TopologyContext([first, database, second])

        self.assertEqual(context.resources_by_type("service"), (first, second))

    def test_resources_by_type_uses_exact_case_match(self) -> None:
        service = _resource("service:api", "service")
        context = TopologyContext([service])

        self.assertEqual(context.resources_by_type("Service"), ())

    def test_resources_by_type_strips_external_whitespace(self) -> None:
        service = _resource("service:api", "service")
        context = TopologyContext([service])

        self.assertEqual(context.resources_by_type(" service "), (service,))

    def test_unknown_resource_type_returns_empty_tuple(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        self.assertEqual(context.resources_by_type("database"), ())

    def test_empty_resource_type_returns_empty_tuple(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        self.assertEqual(context.resources_by_type(" "), ())

    def test_non_string_resource_type_raises_type_error(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        with self.assertRaises(TypeError):
            context.resources_by_type(1)

    def test_len_returns_resource_count(self) -> None:
        context = TopologyContext([
            _resource("service:api", "service"),
            _resource("database:main", "database"),
        ])

        self.assertEqual(len(context), 2)

    def test_context_has_no_public_mutation_methods(self) -> None:
        context = TopologyContext([_resource("a", "service")])

        for method_name in ("add", "add_resource", "clear", "remove"):
            self.assertFalse(hasattr(context, method_name))

    def test_repeated_calls_are_stable(self) -> None:
        context = TopologyContext([
            _resource("a", "service"),
            _resource("b", "database"),
        ])

        self.assertEqual(context.resources(), context.resources())
        self.assertEqual(context.resources_by_type("service"), context.resources_by_type("service"))


def _resource(resource_id: str, resource_type: str) -> Resource:
    return Resource(
        id=resource_id,
        type=resource_type,
        name=resource_id,
        state="active",
    )


if __name__ == "__main__":
    unittest.main()
