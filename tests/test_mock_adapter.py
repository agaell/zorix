import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "modules" / "core_model" / "src"))
sys.path.insert(0, str(ROOT / "modules" / "mock_adapter" / "src"))

from zorix_core_model import Adapter, Resource
from zorix_mock_adapter import MockAdapter


def test_mock_adapter_discover_returns_resources() -> None:
    adapter = MockAdapter()
    resources = adapter.discover()
    resource_types = Counter(resource.type for resource in resources)

    assert isinstance(adapter, Adapter)
    assert all(isinstance(resource, Resource) for resource in resources)
    assert resources[0].id == "mock-service-1"
    assert resource_types["service"] == 2
    assert resource_types["container"] == 1
    assert resource_types["user"] == 2
