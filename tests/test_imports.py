import unittest

import zorix
import zorix_core_model
import zorix_docker_adapter
import zorix_mock_adapter
import zorix_plugin_loader
import zorix_presentation
import zorix_registry
import zorix_resource_graph
import zorix_scan_engine
import zorix_runtime
from zorix_core_model import Adapter, Event, Resource, Tool, Workflow


class PackagingImportTest(unittest.TestCase):
    def test_public_packages_import(self) -> None:
        self.assertEqual(zorix.__version__, "0.1.0")
        self.assertTrue(zorix_core_model)
        self.assertTrue(zorix_docker_adapter)
        self.assertTrue(zorix_mock_adapter)
        self.assertTrue(zorix_plugin_loader)
        self.assertTrue(zorix_presentation)
        self.assertTrue(zorix_registry)
        self.assertTrue(zorix_resource_graph)
        self.assertTrue(zorix_scan_engine)
        self.assertTrue(zorix_runtime)

    def test_core_model_exports_import(self) -> None:
        self.assertTrue(Adapter)
        self.assertTrue(Event)
        self.assertTrue(Resource)
        self.assertTrue(Tool)
        self.assertTrue(Workflow)
