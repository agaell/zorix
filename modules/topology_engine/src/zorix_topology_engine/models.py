from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from zorix_resource_graph import ResourceGraph


class TopologyStatus(Enum):
    SUCCESS = auto()
    PARTIAL = auto()
    FAILED = auto()


@dataclass(frozen=True)
class TopologyProviderError:
    provider: str
    error_type: str
    message: str


@dataclass(frozen=True)
class TopologyResult:
    status: TopologyStatus
    graph: ResourceGraph
    errors: tuple[TopologyProviderError, ...]
    provider_count: int
    successful_provider_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.status, TopologyStatus):
            raise ValueError("status must be TopologyStatus")

        if not isinstance(self.graph, ResourceGraph):
            raise ValueError("graph must be ResourceGraph")

        if not isinstance(self.errors, tuple):
            raise ValueError("errors must be tuple")

        for error in self.errors:
            if not isinstance(error, TopologyProviderError):
                raise ValueError("errors must contain TopologyProviderError")

        _validate_count(self.provider_count, "provider_count")
        _validate_count(self.successful_provider_count, "successful_provider_count")

        if self.successful_provider_count > self.provider_count:
            raise ValueError("successful_provider_count must not exceed provider_count")

        if len(self.errors) != self.failed_provider_count:
            raise ValueError("errors length must match failed provider count")

        if self.status is not _status_for_counts(
            self.provider_count,
            self.successful_provider_count,
        ):
            raise ValueError("status does not match provider statistics")

    @property
    def failed_provider_count(self) -> int:
        return self.provider_count - self.successful_provider_count

    @property
    def relation_count(self) -> int:
        return len(self.graph.relations())


def _validate_count(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")


def _status_for_counts(
    provider_count: int,
    successful_provider_count: int,
) -> TopologyStatus:
    failed_provider_count = provider_count - successful_provider_count

    if provider_count == 0:
        return TopologyStatus.SUCCESS

    if failed_provider_count == 0:
        return TopologyStatus.SUCCESS

    if successful_provider_count > 0:
        return TopologyStatus.PARTIAL

    return TopologyStatus.FAILED
