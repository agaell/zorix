from __future__ import annotations

import copy
import unittest

from zorix_core_model import Resource
from zorix_health_api import HealthContext, HealthProvider
from zorix_health_model import HealthFinding, HealthSeverity
from zorix_resource_graph import DuplicateResourceError, UnknownResourceError


class ExampleHealthProvider:
    def evaluate_health(self, context: HealthContext) -> list[HealthFinding]:
        return [
            HealthFinding("test", "test.info", HealthSeverity.INFO, "r1", "ok")
        ]


class NotAProvider:
    pass


class HealthApiTest(unittest.TestCase):
    def test_resources_preserve_order_and_return_tuple(self) -> None:
        resources = [_resource("r1", "service"), _resource("r2", "filesystem")]
        context = HealthContext(resources)

        self.assertEqual(context.resources(), tuple(resources))
        self.assertIsInstance(context.resources(), tuple)

    def test_resource_lookup(self) -> None:
        resource = _resource("r1", "service")
        context = HealthContext([resource])

        self.assertTrue(context.has_resource("r1"))
        self.assertFalse(context.has_resource("missing"))
        self.assertIs(context.resource("r1"), resource)
        with self.assertRaises(UnknownResourceError):
            context.resource("missing")

    def test_resources_by_type(self) -> None:
        service = _resource("r1", "service")
        filesystem = _resource("r2", "filesystem")
        context = HealthContext([service, filesystem])

        self.assertEqual(context.resources_by_type("service"), (service,))
        self.assertEqual(context.resources_by_type("missing"), ())
        self.assertEqual(context.resources_by_type("   "), ())

    def test_len(self) -> None:
        self.assertEqual(len(HealthContext([_resource("r1", "service")])), 1)

    def test_duplicate_resource_id_is_rejected(self) -> None:
        with self.assertRaises(DuplicateResourceError):
            HealthContext([_resource("r1", "service"), _resource("r1", "service")])

    def test_runtime_structural_health_provider_detection(self) -> None:
        self.assertIsInstance(ExampleHealthProvider(), HealthProvider)
        self.assertNotIsInstance(NotAProvider(), HealthProvider)

    def test_context_does_not_mutate_resources(self) -> None:
        resources = [_resource("r1", "service")]
        before = copy.deepcopy(resources)

        context = HealthContext(resources)

        self.assertEqual(resources, before)
        self.assertIs(context.resources()[0], resources[0])


def _resource(resource_id: str, resource_type: str) -> Resource:
    return Resource(resource_id, resource_type, resource_id, "active")


if __name__ == "__main__":
    unittest.main()
