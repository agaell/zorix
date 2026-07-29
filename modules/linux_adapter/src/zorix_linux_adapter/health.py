from __future__ import annotations

from zorix_core_model import Resource
from zorix_health_api import HealthContext
from zorix_health_model import HealthFinding, HealthSeverity


def evaluate_linux_health(*, target: str, context: HealthContext) -> list[HealthFinding]:
    findings: list[HealthFinding] = []

    for resource in context.resources():
        service_finding = _service_finding(target, resource)
        if service_finding is not None:
            findings.append(service_finding)
            continue

        filesystem_finding = _filesystem_finding(target, resource)
        if filesystem_finding is not None:
            findings.append(filesystem_finding)
            continue

        memory_finding = _memory_finding(target, resource)
        if memory_finding is not None:
            findings.append(memory_finding)

    return findings


def _service_finding(target: str, resource: Resource) -> HealthFinding | None:
    if resource.type != "service":
        return None
    if not resource.id.startswith(f"linux:service:{target}:"):
        return None
    if resource.metadata.get("host_id") != _host_id(target):
        return None
    if not _service_failed(resource):
        return None

    metadata = _non_empty_metadata(
        {
            "unit": resource.metadata.get("unit"),
            "active_state": resource.metadata.get("active_state"),
            "sub_state": resource.metadata.get("sub_state"),
        }
    )

    return HealthFinding(
        source="linux",
        code="linux.service.failed",
        severity=HealthSeverity.CRITICAL,
        resource_id=resource.id,
        message=f"Service {resource.name} is failed",
        metadata=metadata,
    )


def _filesystem_finding(target: str, resource: Resource) -> HealthFinding | None:
    if resource.type != "filesystem":
        return None
    if not resource.id.startswith(f"linux:filesystem:{target}:"):
        return None
    if resource.metadata.get("host_id") != _host_id(target):
        return None

    usage_percent = _integer_percent(resource.metadata.get("usage_percent"))
    if usage_percent is None:
        return None
    if usage_percent < 80:
        return None

    severity = (
        HealthSeverity.CRITICAL
        if usage_percent >= 90
        else HealthSeverity.WARNING
    )
    metadata = _non_empty_metadata(
        {
            "mountpoint": resource.metadata.get("mountpoint"),
            "usage_percent": str(usage_percent),
            "available_bytes": resource.metadata.get("available_bytes"),
            "size_bytes": resource.metadata.get("size_bytes"),
        }
    )

    return HealthFinding(
        source="linux",
        code="linux.filesystem.usage_high",
        severity=severity,
        resource_id=resource.id,
        message=f"Filesystem {resource.name} usage is {usage_percent}%",
        metadata=metadata,
    )


def _memory_finding(target: str, resource: Resource) -> HealthFinding | None:
    if resource.type != "memory":
        return None
    if resource.id != f"linux:memory:{target}":
        return None
    if resource.metadata.get("host_id") != _host_id(target):
        return None

    total_bytes = _integer_value(resource.metadata.get("total_bytes"))
    available_bytes = _integer_value(resource.metadata.get("available_bytes"))
    if total_bytes is None or available_bytes is None:
        return None
    if total_bytes <= 0:
        return None
    if available_bytes < 0 or available_bytes > total_bytes:
        return None

    available_percent = available_bytes / total_bytes * 100
    if available_percent > 20:
        return None

    severity = (
        HealthSeverity.CRITICAL
        if available_percent <= 10
        else HealthSeverity.WARNING
    )
    formatted_percent = f"{available_percent:.2f}"

    return HealthFinding(
        source="linux",
        code="linux.memory.available_low",
        severity=severity,
        resource_id=resource.id,
        message=f"Available memory is {formatted_percent}% of total",
        metadata={
            "available_bytes": str(available_bytes),
            "total_bytes": str(total_bytes),
            "available_percent": formatted_percent,
        },
    )


def _service_failed(resource: Resource) -> bool:
    values = (
        resource.state,
        resource.metadata.get("active_state"),
        resource.metadata.get("sub_state"),
    )
    return any(_normalized(value) == "failed" for value in values)


def _integer_percent(value: object) -> int | None:
    integer = _integer_value(value)
    if integer is None or integer < 0 or integer > 100:
        return None
    return integer


def _integer_value(value: object) -> int | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text.isdigit():
        return None

    return int(text)


def _non_empty_metadata(values: dict[str, object]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(value, str):
            continue

        text = value.strip()
        if text:
            metadata[key] = text

    return metadata


def _normalized(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _host_id(target: str) -> str:
    return f"linux:host:{target}"
