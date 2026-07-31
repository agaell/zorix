from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from .model import ActionPlan, ActionRequest, _metadata, _required_text


class ActionExecutionStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ActionExecutionRejection:
    code: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(self, "message", _required_text(self.message, "message"))


@dataclass(frozen=True)
class ActionExecutionResult:
    status: ActionExecutionStatus
    request: ActionRequest
    plan: ActionPlan | None
    previous_state: str | None
    current_state: str | None
    changed: bool
    verified: bool
    message: str
    rejection: ActionExecutionRejection | None = None
    metadata: Mapping[str, str] = field(
        default_factory=dict,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.status, ActionExecutionStatus):
            raise ValueError("status must be ActionExecutionStatus")
        if not isinstance(self.request, ActionRequest):
            raise ValueError("request must be ActionRequest")
        if self.plan is not None and not isinstance(self.plan, ActionPlan):
            raise ValueError("plan must be ActionPlan or None")
        if not isinstance(self.changed, bool):
            raise ValueError("changed must be bool")
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be bool")

        object.__setattr__(self, "previous_state", _optional_state(self.previous_state))
        object.__setattr__(self, "current_state", _optional_state(self.current_state))
        object.__setattr__(self, "message", _required_text(self.message, "message"))
        object.__setattr__(self, "metadata", MappingProxyType(_metadata(self.metadata)))

        if self.status is ActionExecutionStatus.SUCCESS:
            if self.plan is None:
                raise ValueError("SUCCESS result requires plan")
            if self.rejection is not None:
                raise ValueError("SUCCESS result must not contain rejection")
            if not self.verified:
                raise ValueError("SUCCESS result requires verified=True")
            if self.current_state is None:
                raise ValueError("SUCCESS result requires current_state")
            return

        if self.status is ActionExecutionStatus.FAILED:
            if self.plan is None:
                raise ValueError("FAILED result requires plan")
            if self.rejection is not None:
                raise ValueError("FAILED result must not contain rejection")
            return

        if self.status is ActionExecutionStatus.REJECTED:
            if not isinstance(self.rejection, ActionExecutionRejection):
                raise ValueError("REJECTED result requires rejection")
            if self.verified:
                raise ValueError("REJECTED result requires verified=False")
            if self.changed:
                raise ValueError("REJECTED result requires changed=False")
            if self.previous_state is not None:
                raise ValueError("REJECTED result requires previous_state=None")
            if self.current_state is not None:
                raise ValueError("REJECTED result requires current_state=None")


def _optional_state(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("state must be a string or None")

    text = value.strip()
    if not text:
        return None
    return text
