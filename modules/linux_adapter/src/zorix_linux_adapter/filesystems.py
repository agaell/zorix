from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from zorix_core_model import Resource

from .inventory import host_resource_id


_EXCLUDED_FILESYSTEM_TYPES = {
    "tmpfs",
    "devtmpfs",
    "proc",
    "sysfs",
    "cgroup",
    "cgroup2",
    "debugfs",
    "tracefs",
    "securityfs",
    "pstore",
    "efivarfs",
    "mqueue",
    "hugetlbfs",
    "fusectl",
    "configfs",
    "autofs",
    "rpc_pipefs",
    "squashfs",
    "overlay",
}


@dataclass(frozen=True)
class FilesystemSnapshot:
    source: str
    filesystem_type: str
    size_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: int | None
    mountpoint: str


def parse_filesystems(output: str) -> list[FilesystemSnapshot]:
    filesystems: list[FilesystemSnapshot] = []

    for line in output.splitlines():
        parts = line.strip().split(None, 6)
        if len(parts) != 7:
            continue

        source, filesystem_type, size, used, available, percentage, mountpoint = parts
        filesystem_type = filesystem_type.strip()
        if (
            not source.strip()
            or not filesystem_type
            or not mountpoint.strip()
            or filesystem_type.lower() in _EXCLUDED_FILESYSTEM_TYPES
        ):
            continue

        size_bytes = _non_negative_int(size)
        used_bytes = _non_negative_int(used)
        available_bytes = _non_negative_int(available)
        if size_bytes is None or used_bytes is None or available_bytes is None:
            continue

        filesystems.append(
            FilesystemSnapshot(
                source=source.strip(),
                filesystem_type=filesystem_type,
                size_bytes=size_bytes,
                used_bytes=used_bytes,
                available_bytes=available_bytes,
                usage_percent=_usage_percent(percentage),
                mountpoint=mountpoint.strip(),
            )
        )

    return filesystems


def filesystems_to_resources(
    *,
    target: str,
    filesystems_output: str,
) -> list[Resource]:
    host_id = host_resource_id(target)
    resources: list[Resource] = []
    seen_resource_ids: set[str] = set()

    for filesystem in parse_filesystems(filesystems_output):
        resource_id = f"linux:filesystem:{target}:{quote(filesystem.mountpoint, safe='')}"
        if resource_id in seen_resource_ids:
            continue

        seen_resource_ids.add(resource_id)
        metadata = {
            "host_id": host_id,
            "source": filesystem.source,
            "filesystem_type": filesystem.filesystem_type,
            "size_bytes": str(filesystem.size_bytes),
            "used_bytes": str(filesystem.used_bytes),
            "available_bytes": str(filesystem.available_bytes),
            "mountpoint": filesystem.mountpoint,
        }
        if filesystem.usage_percent is not None:
            metadata["usage_percent"] = str(filesystem.usage_percent)

        resources.append(
            Resource(
                id=resource_id,
                type="filesystem",
                name=filesystem.mountpoint,
                state="mounted",
                metadata=metadata,
                labels={},
            )
        )

    return resources


def _non_negative_int(value: str) -> int | None:
    try:
        number = int(value)
    except ValueError:
        return None

    if number < 0:
        return None

    return number


def _usage_percent(value: str) -> int | None:
    if not value.endswith("%"):
        return None

    return _non_negative_int(value[:-1])
