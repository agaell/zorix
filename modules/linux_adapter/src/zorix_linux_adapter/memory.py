from __future__ import annotations

from collections.abc import Mapping

from zorix_core_model import Resource

from .errors import LinuxOutputError
from .inventory import host_resource_id


_SUPPORTED_KEYS = {
    "MemTotal",
    "MemFree",
    "MemAvailable",
    "Buffers",
    "Cached",
    "SReclaimable",
    "Shmem",
    "SwapTotal",
    "SwapFree",
}


def parse_meminfo(output: str) -> Mapping[str, int]:
    values: dict[str, int] = {}

    for line in output.splitlines():
        if ":" not in line:
            continue

        key, raw_value = line.split(":", 1)
        normalized_key = key.strip()
        if normalized_key not in _SUPPORTED_KEYS or normalized_key in values:
            continue

        parts = raw_value.strip().split()
        if len(parts) < 2 or parts[1] != "kB":
            continue

        try:
            value = int(parts[0])
        except ValueError:
            continue

        if value < 0:
            continue

        values[normalized_key] = value * 1024

    if "MemTotal" not in values:
        raise LinuxOutputError("/proc/meminfo is missing a valid MemTotal value")

    return values


def memory_to_resource(
    *,
    target: str,
    meminfo_output: str,
) -> Resource:
    meminfo = parse_meminfo(meminfo_output)
    host_id = host_resource_id(target)
    metadata: dict[str, str] = {}

    _add_metadata(metadata, "host_id", host_id)
    _add_int_metadata(metadata, "total_bytes", meminfo.get("MemTotal"))
    _add_int_metadata(metadata, "available_bytes", meminfo.get("MemAvailable"))
    _add_int_metadata(metadata, "free_bytes", meminfo.get("MemFree"))
    _add_int_metadata(metadata, "buffers_bytes", meminfo.get("Buffers"))
    _add_int_metadata(metadata, "cached_bytes", meminfo.get("Cached"))
    _add_int_metadata(metadata, "swap_total_bytes", meminfo.get("SwapTotal"))
    _add_int_metadata(metadata, "swap_free_bytes", meminfo.get("SwapFree"))

    total_bytes = meminfo["MemTotal"]
    available_bytes = meminfo.get("MemAvailable")
    if available_bytes is not None:
        used_bytes = total_bytes - available_bytes
        if used_bytes >= 0:
            _add_int_metadata(metadata, "used_bytes", used_bytes)
            if total_bytes > 0:
                metadata["usage_percent"] = f"{(used_bytes / total_bytes * 100):.2f}"

    swap_total = meminfo.get("SwapTotal")
    swap_free = meminfo.get("SwapFree")
    if swap_total is not None and swap_free is not None:
        swap_used = swap_total - swap_free
        if swap_used >= 0:
            _add_int_metadata(metadata, "swap_used_bytes", swap_used)

    return Resource(
        id=f"linux:memory:{target}",
        type="memory",
        name="System memory",
        state="present",
        metadata=metadata,
        labels={},
    )


def _add_metadata(metadata: dict[str, str], key: str, value: str) -> None:
    if value:
        metadata[key] = value


def _add_int_metadata(metadata: dict[str, str], key: str, value: int | None) -> None:
    if value is not None:
        metadata[key] = str(value)
