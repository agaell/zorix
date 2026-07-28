from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from zorix_core_model import Resource


class ScanStatus(Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AdapterScanError:
    adapter: str
    error_type: str
    message: str


@dataclass(frozen=True)
class ScanResult:
    status: ScanStatus
    resources: tuple[Resource, ...]
    errors: tuple[AdapterScanError, ...]

    @property
    def succeeded(self) -> bool:
        return self.status is ScanStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status is ScanStatus.FAILED

    @property
    def partial(self) -> bool:
        return self.status is ScanStatus.PARTIAL
