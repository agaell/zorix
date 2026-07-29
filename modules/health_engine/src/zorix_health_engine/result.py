from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from zorix_health_model import (
    HealthFinding,
    HealthLevel,
    HealthSeverity,
    health_level_for_findings,
)


class HealthStatus(Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True)
class HealthProviderError:
    provider: str
    error_type: str
    message: str


@dataclass(frozen=True)
class HealthResult:
    status: HealthStatus
    level: HealthLevel
    findings: tuple[HealthFinding, ...]
    errors: tuple[HealthProviderError, ...]
    provider_count: int
    successful_provider_count: int
    resource_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.status, HealthStatus):
            raise ValueError("status must be HealthStatus")
        if not isinstance(self.level, HealthLevel):
            raise ValueError("level must be HealthLevel")
        if not isinstance(self.findings, tuple):
            raise ValueError("findings must be tuple")
        if not isinstance(self.errors, tuple):
            raise ValueError("errors must be tuple")

        for finding in self.findings:
            if not isinstance(finding, HealthFinding):
                raise ValueError("findings must contain HealthFinding")
        for error in self.errors:
            if not isinstance(error, HealthProviderError):
                raise ValueError("errors must contain HealthProviderError")

        _validate_count(self.provider_count, "provider_count")
        _validate_count(self.successful_provider_count, "successful_provider_count")
        _validate_count(self.resource_count, "resource_count")

        if self.successful_provider_count > self.provider_count:
            raise ValueError("successful_provider_count must not exceed provider_count")
        if len(self.errors) != self.failed_provider_count:
            raise ValueError("errors length must match failed provider count")
        if self.status is not _status_for_counts(
            self.provider_count,
            self.successful_provider_count,
        ):
            raise ValueError("status does not match provider statistics")
        if self.level is not health_level_for_findings(self.findings):
            raise ValueError("level does not match findings")

    @property
    def failed_provider_count(self) -> int:
        return self.provider_count - self.successful_provider_count

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return _severity_count(self.findings, HealthSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return _severity_count(self.findings, HealthSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return _severity_count(self.findings, HealthSeverity.INFO)


def _severity_count(
    findings: tuple[HealthFinding, ...],
    severity: HealthSeverity,
) -> int:
    return sum(1 for finding in findings if finding.severity is severity)


def _validate_count(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _status_for_counts(
    provider_count: int,
    successful_provider_count: int,
) -> HealthStatus:
    failed_provider_count = provider_count - successful_provider_count

    if provider_count == 0:
        return HealthStatus.SUCCESS
    if failed_provider_count == 0:
        return HealthStatus.SUCCESS
    if successful_provider_count > 0:
        return HealthStatus.PARTIAL
    return HealthStatus.FAILED
