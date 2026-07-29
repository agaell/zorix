from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType


class ActionRisk(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ActionRequest:
    action: str
    resource_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", _required_text(self.action, "action"))
        object.__setattr__(
            self,
            "resource_id",
            _required_text(self.resource_id, "resource_id"),
        )


@dataclass(frozen=True)
class ActionStep:
    position: int
    code: str
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.position, int) or isinstance(self.position, bool):
            raise ValueError("position must be an integer")
        if self.position <= 0:
            raise ValueError("position must be positive")

        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(
            self,
            "description",
            _required_text(self.description, "description"),
        )


@dataclass(frozen=True)
class ActionPlan:
    source: str
    provider: str
    request: ActionRequest
    resource_name: str
    operation: str
    risk: ActionRisk
    requires_confirmation: bool
    summary: str
    steps: tuple[ActionStep, ...]
    metadata: Mapping[str, str] = field(
        default_factory=dict,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.request, ActionRequest):
            raise ValueError("request must be ActionRequest")
        if not isinstance(self.risk, ActionRisk):
            raise ValueError("risk must be ActionRisk")
        if not isinstance(self.requires_confirmation, bool):
            raise ValueError("requires_confirmation must be bool")
        if not isinstance(self.steps, tuple):
            raise ValueError("steps must be tuple")
        if not self.steps:
            raise ValueError("steps must not be empty")

        for expected_position, step in enumerate(self.steps, start=1):
            if not isinstance(step, ActionStep):
                raise ValueError("steps must contain ActionStep")
            if step.position != expected_position:
                raise ValueError("step positions must be sequential")

        object.__setattr__(self, "source", _required_text(self.source, "source"))
        object.__setattr__(self, "provider", _required_text(self.provider, "provider"))
        object.__setattr__(
            self,
            "resource_name",
            _required_text(self.resource_name, "resource_name"),
        )
        object.__setattr__(
            self,
            "operation",
            _required_text(self.operation, "operation"),
        )
        object.__setattr__(self, "summary", _required_text(self.summary, "summary"))
        object.__setattr__(self, "metadata", MappingProxyType(_metadata(self.metadata)))

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.source, self.request.action, self.request.resource_id)


class ActionPlanStatus(Enum):
    READY = "READY"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ActionRejection:
    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(self, "message", _required_text(self.message, "message"))


@dataclass(frozen=True)
class ActionPlanResult:
    status: ActionPlanStatus
    request: ActionRequest
    plan: ActionPlan | None = None
    rejection: ActionRejection | None = None
    provider_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.status, ActionPlanStatus):
            raise ValueError("status must be ActionPlanStatus")
        if not isinstance(self.request, ActionRequest):
            raise ValueError("request must be ActionRequest")
        if not isinstance(self.provider_count, int) or isinstance(self.provider_count, bool):
            raise ValueError("provider_count must be an integer")
        if self.provider_count < 0:
            raise ValueError("provider_count must be non-negative")

        if self.status is ActionPlanStatus.READY:
            if not isinstance(self.plan, ActionPlan):
                raise ValueError("READY result requires plan")
            if self.rejection is not None:
                raise ValueError("READY result must not contain rejection")
            return

        if self.status is ActionPlanStatus.REJECTED:
            if self.plan is not None:
                raise ValueError("REJECTED result must not contain plan")
            if not isinstance(self.rejection, ActionRejection):
                raise ValueError("REJECTED result requires rejection")


def risk_rank(risk: ActionRisk) -> int:
    if risk is ActionRisk.LOW:
        return 1
    if risk is ActionRisk.MEDIUM:
        return 2
    if risk is ActionRisk.HIGH:
        return 3
    if risk is ActionRisk.CRITICAL:
        return 4

    raise ValueError("risk must be ActionRisk")


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")

    return text


def _metadata(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError("metadata must be a mapping")

    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("metadata keys must be strings")
        if not isinstance(item, str):
            raise ValueError("metadata values must be strings")
        result[key] = item

    return result
