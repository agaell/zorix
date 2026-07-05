from dataclasses import dataclass, field
from typing import Any


@dataclass
class Resource:
    id: str
    type: str
    name: str
    state: str
    metadata: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
