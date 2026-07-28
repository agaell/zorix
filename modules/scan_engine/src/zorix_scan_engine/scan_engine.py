from __future__ import annotations

from zorix_core_model import Adapter, Resource
from zorix_registry import Registry

from .models import AdapterScanError, ScanResult, ScanStatus


class ScanEngine:
    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def scan(self, *, continue_on_error: bool = False) -> ScanResult:
        resources: list[Resource] = []
        errors: list[AdapterScanError] = []

        for adapter in self._registry.adapters():
            try:
                resources.extend(adapter.discover())
            except Exception as exc:
                if not continue_on_error:
                    raise

                errors.append(_adapter_error(adapter, exc))

        return ScanResult(
            status=_scan_status(resources, errors),
            resources=tuple(resources),
            errors=tuple(errors),
        )


def _adapter_error(adapter: Adapter, exc: Exception) -> AdapterScanError:
    return AdapterScanError(
        adapter=_adapter_class_name(adapter),
        error_type=type(exc).__name__,
        message=str(exc),
    )


def _adapter_class_name(adapter: Adapter) -> str:
    adapter_type = type(adapter)
    return f"{adapter_type.__module__}.{adapter_type.__qualname__}"


def _scan_status(resources: list[Resource], errors: list[AdapterScanError]) -> ScanStatus:
    if not errors:
        return ScanStatus.SUCCESS

    if resources:
        return ScanStatus.PARTIAL

    return ScanStatus.FAILED
