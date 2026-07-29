import unittest

import zorix
import zorix_action_api
import zorix_action_engine
import zorix_action_model
import zorix_core_model
import zorix_docker_adapter
import zorix_health_api
import zorix_health_engine
import zorix_health_model
import zorix_linux_adapter
import zorix_mock_adapter
import zorix_plugin_loader
import zorix_presentation
import zorix_registry
import zorix_resource_graph
import zorix_scan_engine
import zorix_runtime
import zorix_topology_api
import zorix_topology_engine
from zorix_core_model import Adapter, Event, Resource, Tool, Workflow
from zorix_action_engine import ActionEngine
from zorix_action_model import ActionPlan, ActionPlanResult, ActionRequest, ActionRisk
from zorix_presentation import ActionPlanConsoleRenderer
from zorix_health_engine import HealthEngine
from zorix_health_model import HealthFinding, HealthLevel, HealthSeverity
from zorix_presentation import HealthConsoleRenderer


class PackagingImportTest(unittest.TestCase):
    def test_public_packages_import(self) -> None:
        self.assertEqual(zorix.__version__, "0.1.0")
        self.assertTrue(zorix_action_api)
        self.assertTrue(zorix_action_engine)
        self.assertTrue(zorix_action_model)
        self.assertTrue(zorix_core_model)
        self.assertTrue(zorix_docker_adapter)
        self.assertTrue(zorix_health_api)
        self.assertTrue(zorix_health_engine)
        self.assertTrue(zorix_health_model)
        self.assertTrue(zorix_linux_adapter)
        self.assertTrue(zorix_mock_adapter)
        self.assertTrue(zorix_plugin_loader)
        self.assertTrue(zorix_presentation)
        self.assertTrue(zorix_registry)
        self.assertTrue(zorix_resource_graph)
        self.assertTrue(zorix_scan_engine)
        self.assertTrue(zorix_runtime)
        self.assertTrue(zorix_topology_api)
        self.assertTrue(zorix_topology_engine)

    def test_core_model_exports_import(self) -> None:
        self.assertTrue(Adapter)
        self.assertTrue(Event)
        self.assertTrue(Resource)
        self.assertTrue(Tool)
        self.assertTrue(Workflow)

    def test_action_exports_import(self) -> None:
        self.assertTrue(ActionRisk)
        self.assertTrue(ActionRequest)
        self.assertTrue(ActionPlan)
        self.assertTrue(ActionPlanResult)
        self.assertTrue(ActionEngine)
        self.assertTrue(ActionPlanConsoleRenderer)

    def test_health_exports_import(self) -> None:
        self.assertTrue(HealthSeverity)
        self.assertTrue(HealthLevel)
        self.assertTrue(HealthFinding)
        self.assertTrue(HealthEngine)
        self.assertTrue(HealthConsoleRenderer)
