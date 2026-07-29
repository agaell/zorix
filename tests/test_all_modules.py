from __future__ import annotations

import importlib.util
import sys
from types import ModuleType
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_TEST_DIRS = [
    ROOT / "modules" / "core_model" / "tests",
    ROOT / "modules" / "docker_adapter" / "tests",
    ROOT / "modules" / "mock_adapter" / "tests",
    ROOT / "modules" / "plugin_loader" / "tests",
    ROOT / "modules" / "presentation" / "tests",
    ROOT / "modules" / "registry" / "tests",
    ROOT / "modules" / "resource_graph" / "tests",
    ROOT / "modules" / "scan_engine" / "tests",
    ROOT / "modules" / "runtime" / "tests",
    ROOT / "modules" / "topology_api" / "tests",
]


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    test_pattern = pattern or "test*.py"

    for test_dir in MODULE_TEST_DIRS:
        if test_dir.is_dir():
            for test_file in sorted(test_dir.glob(test_pattern)):
                module = _load_test_module(test_file)
                suite.addTests(loader.loadTestsFromModule(module))

    return suite


def _load_test_module(test_file: Path) -> ModuleType:
    module_name = f"_zorix_{test_file.parent.parent.name}_{test_file.stem}"
    spec = importlib.util.spec_from_file_location(module_name, test_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load test module from {test_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
