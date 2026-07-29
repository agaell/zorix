from __future__ import annotations

import copy
import unittest

from zorix_action_api import ActionContext, ActionProvider
from zorix_action_model import ActionPlan, ActionRequest, ActionRisk, ActionStep
from zorix_core_model import Resource
from zorix_resource_graph import DuplicateResourceError, UnknownResourceError


class ExampleProvider:
    def plan_action(self, context: ActionContext, request: ActionRequest) -> ActionPlan | None:
        return None


class NotProvider:
    pass


class ActionApiTest(unittest.TestCase):
    def test_resource_order_and_tuple(self) -> None:
        resources = [_resource("r1", "service"), _resource("r2", "filesystem")]
        context = ActionContext(resources)

        self.assertEqual(context.resources(), tuple(resources))
        self.assertIsInstance(context.resources(), tuple)

    def test_lookup(self) -> None:
        resource = _resource("r1", "service")
        context = ActionContext([resource])

        self.assertTrue(context.has_resource("r1"))
        self.assertFalse(context.has_resource("missing"))
        self.assertIs(context.resource("r1"), resource)
        with self.assertRaises(UnknownResourceError):
            context.resource("missing")

    def test_resources_by_type_len_and_duplicate_id(self) -> None:
        service = _resource("r1", "service")
        context = ActionContext([service, _resource("r2", "filesystem")])

        self.assertEqual(context.resources_by_type("service"), (service,))
        self.assertEqual(context.resources_by_type(" "), ())
        self.assertEqual(len(context), 2)
        with self.assertRaises(DuplicateResourceError):
            ActionContext([_resource("r1", "service"), _resource("r1", "service")])

    def test_action_provider_runtime_protocol(self) -> None:
        self.assertIsInstance(ExampleProvider(), ActionProvider)
        self.assertNotIsInstance(NotProvider(), ActionProvider)

    def test_context_does_not_mutate_resources(self) -> None:
        resources = [_resource("r1", "service")]
        before = copy.deepcopy(resources)

        context = ActionContext(resources)

        self.assertEqual(resources, before)
        self.assertIs(context.resources()[0], resources[0])


def _resource(resource_id: str, resource_type: str) -> Resource:
    return Resource(resource_id, resource_type, resource_id, "active")


if __name__ == "__main__":
    unittest.main()
