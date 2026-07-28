import sys
from pathlib import Path


CORE_MODEL_SRC = Path(__file__).resolve().parents[1] / "modules" / "core_model" / "src"
sys.path.insert(0, str(CORE_MODEL_SRC))

from zorix_core_model import Adapter, Event, Resource, Tool, Workflow


def test_core_model_imports() -> None:
    assert Adapter
    assert Event
    assert Resource
    assert Tool
    assert Workflow
