from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType


class HealthSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class HealthLevel(Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class HealthFinding:
    source: str
    code: str
    severity: HealthSeverity
    resource_id: str
    message: str
    metadata: Mapping[str, str] = field(
        default_factory=dict,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        source = _required_text(self.source, "source")
        code = _required_text(self.code, "code")
        resource_id = _required_text(self.resource_id, "resource_id")
        message = _required_text(self.message, "message")

        if not isinstance(self.severity, HealthSeverity):
            raise ValueError("severity must be HealthSeverity")

        metadata = _metadata(self.metadata)

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "resource_id", resource_id)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "metadata", MappingProxyType(metadata))

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.source, self.code, self.resource_id)


def health_level_for_findings(findings: tuple[HealthFinding, ...]) -> HealthLevel:
    if any(finding.severity is HealthSeverity.CRITICAL for finding in findings):
        return HealthLevel.CRITICAL

    if any(finding.severity is HealthSeverity.WARNING for finding in findings):
        return HealthLevel.WARNING

    return HealthLevel.HEALTHY


def severity_rank(severity: HealthSeverity) -> int:
    if severity is HealthSeverity.INFO:
        return 1
    if severity is HealthSeverity.WARNING:
        return 2
    if severity is HealthSeverity.CRITICAL:
        return 3

    raise ValueError("severity must be HealthSeverity")


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
