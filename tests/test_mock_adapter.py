from collections import Counter
import unittest


from zorix_core_model import Adapter, Resource
from zorix_mock_adapter import MockAdapter


class MockAdapterTest(unittest.TestCase):
    def test_mock_adapter_discover_returns_resources(self) -> None:
        adapter = MockAdapter()
        resources = adapter.discover()
        resource_types = Counter(resource.type for resource in resources)

        self.assertIsInstance(adapter, Adapter)
        self.assertTrue(all(isinstance(resource, Resource) for resource in resources))
        self.assertEqual(resources[0].id, "mock-service-1")
        self.assertEqual(resource_types["service"], 2)
        self.assertEqual(resource_types["container"], 1)
        self.assertEqual(resource_types["user"], 2)
