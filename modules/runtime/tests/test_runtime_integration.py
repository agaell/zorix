from __future__ import annotations

from collections import Counter
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "modules" / "core_model" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "plugin_loader" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "registry" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "scan_engine" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "runtime" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "mock_adapter" / "src"))

from zorix_scan_engine import ScanStatus
from zorix_runtime import ZorixRuntime


class RuntimeIntegrationTest(unittest.TestCase):
    def test_plugin_loader_registry_scan_engine_chain(self) -> None:
        runtime = ZorixRuntime()

        adapters = runtime.load_plugins(ROOT / "modules" / "mock_adapter")
        result = runtime.scan()
        resource_types = Counter(resource.type for resource in result.resources)

        self.assertEqual(len(adapters), 1)
        self.assertEqual(runtime.adapters(), adapters)
        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(result.resources), 5)
        self.assertEqual(resource_types["service"], 2)
        self.assertEqual(resource_types["container"], 1)
        self.assertEqual(resource_types["user"], 2)


if __name__ == "__main__":
    unittest.main()
