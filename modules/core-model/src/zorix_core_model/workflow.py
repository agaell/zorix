from dataclasses import dataclass, field


@dataclass
class Workflow:
    id: str
    name: str
    tool_ids: list[str] = field(default_factory=list)
