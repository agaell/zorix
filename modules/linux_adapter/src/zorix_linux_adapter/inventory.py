from __future__ import annotations

import re

from zorix_core_model import Resource

from .errors import LinuxConfigurationError


_TARGET_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SERVICE_MARKERS = {"●", "○", "×"}


def validate_target(target: str) -> str:
    normalized = target.strip() if isinstance(target, str) else ""
    if not _TARGET_PATTERN.fullmatch(normalized):
        raise LinuxConfigurationError(
            "SSH target must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}"
        )

    return normalized


def host_to_resource(
    *,
    target: str,
    hostname_output: str,
    kernel_output: str,
    architecture_output: str,
    os_release_output: str,
) -> Resource:
    host_id = host_resource_id(target)
    hostname = _optional_string(hostname_output) or target
    os_release = parse_os_release(os_release_output)
    metadata: dict[str, str] = {}

    _add_metadata(metadata, "ssh_target", target)
    _add_metadata(metadata, "kernel", _optional_string(kernel_output))
    _add_metadata(metadata, "architecture", _optional_string(architecture_output))
    _add_metadata(metadata, "os_id", os_release.get("ID"))
    _add_metadata(metadata, "os_name", os_release.get("PRETTY_NAME") or os_release.get("NAME"))
    _add_metadata(metadata, "os_version", os_release.get("VERSION_ID"))

    return Resource(
        id=host_id,
        type="host",
        name=hostname,
        state="reachable",
        metadata=metadata,
        labels={},
    )


def services_to_resources(
    *,
    target: str,
    systemctl_output: str,
) -> list[Resource]:
    host_id = host_resource_id(target)
    resources: list[Resource] = []
    seen_resource_ids: set[str] = set()

    for service in parse_systemctl_services(systemctl_output):
        resource_id = service_resource_id(target, service["unit"])
        if resource_id in seen_resource_ids:
            continue

        seen_resource_ids.add(resource_id)
        metadata: dict[str, str] = {}
        _add_metadata(metadata, "host_id", host_id)
        _add_metadata(metadata, "unit", service["unit"])
        _add_metadata(metadata, "load_state", service.get("load_state"))
        _add_metadata(metadata, "active_state", service.get("active_state"))
        _add_metadata(metadata, "sub_state", service.get("sub_state"))
        _add_metadata(metadata, "description", service.get("description"))

        resources.append(
            Resource(
                id=resource_id,
                type="service",
                name=service["unit"],
                state=service.get("active_state") or "unknown",
                metadata=metadata,
                labels={},
            )
        )

    return resources


def parse_os_release(output: str) -> dict[str, str]:
    values: dict[str, str] = {}

    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, raw_value = stripped.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue

        value = _unquote_os_release_value(raw_value.strip())
        if value is not None:
            values[normalized_key] = value

    return values


def parse_systemctl_services(output: str) -> list[dict[str, str]]:
    services: list[dict[str, str]] = []

    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        normalized_line = _remove_service_marker(stripped)
        if not normalized_line:
            continue

        parts = normalized_line.split(None, 4)

        if len(parts) < 4:
            continue

        unit = parts[0].strip()
        if not unit or not unit.endswith(".service"):
            continue

        service = {
            "unit": unit,
            "load_state": parts[1].strip(),
            "active_state": parts[2].strip(),
            "sub_state": parts[3].strip(),
        }
        if len(parts) > 4 and parts[4].strip():
            service["description"] = parts[4].strip()

        services.append(service)

    return services


def _remove_service_marker(line: str) -> str:
    if line and line[0] in _SERVICE_MARKERS:
        return line[1:].strip()

    return line


def host_resource_id(target: str) -> str:
    return f"linux:host:{target}"


def service_resource_id(target: str, unit: str) -> str:
    return f"linux:service:{target}:{unit}"


def _unquote_os_release_value(value: str) -> str | None:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]

    text = value.strip()
    if not text:
        return None

    return text


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    return text


def _add_metadata(
    metadata: dict[str, str],
    key: str,
    value: str | None,
) -> None:
    if value is not None:
        metadata[key] = value
