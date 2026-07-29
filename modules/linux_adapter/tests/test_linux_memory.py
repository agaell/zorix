from __future__ import annotations

import copy
import unittest

from zorix_linux_adapter.errors import LinuxOutputError
from zorix_linux_adapter.memory import memory_to_resource, parse_meminfo


class LinuxMemoryTest(unittest.TestCase):
    def test_parse_meminfo_values_and_kb_to_bytes(self) -> None:
        output = _meminfo()

        values = parse_meminfo(output)

        self.assertEqual(values["MemTotal"], 8192000 * 1024)
        self.assertEqual(values["MemFree"], 1000000 * 1024)
        self.assertEqual(values["MemAvailable"], 4096000 * 1024)
        self.assertEqual(values["Buffers"], 200000 * 1024)
        self.assertEqual(values["Cached"], 3000000 * 1024)
        self.assertEqual(values["SwapTotal"], 2097152 * 1024)
        self.assertEqual(values["SwapFree"], 1048576 * 1024)

    def test_parse_meminfo_ignores_unknown_malformed_invalid_and_duplicate_values(self) -> None:
        output = (
            "MemTotal: 100 kB\n"
            "Unknown: 1 kB\n"
            "Malformed\n"
            "MemFree: nope kB\n"
            "MemAvailable: -1 kB\n"
            "Buffers: 1 MB\n"
            "Cached: 2 kB\n"
            "Cached: 3 kB\n"
        )

        values = parse_meminfo(output)

        self.assertEqual(values, {"MemTotal": 102400, "Cached": 2048})

    def test_missing_memtotal_raises_output_error(self) -> None:
        with self.assertRaises(LinuxOutputError):
            parse_meminfo("MemAvailable: 1 kB\n")

    def test_memory_resource_mapping_and_calculations(self) -> None:
        resource = memory_to_resource(target="tandem", meminfo_output=_meminfo())

        self.assertEqual(resource.id, "linux:memory:tandem")
        self.assertEqual(resource.type, "memory")
        self.assertEqual(resource.name, "System memory")
        self.assertEqual(resource.state, "present")
        self.assertEqual(resource.labels, {})
        self.assertEqual(resource.metadata["host_id"], "linux:host:tandem")
        self.assertEqual(resource.metadata["total_bytes"], str(8192000 * 1024))
        self.assertEqual(resource.metadata["available_bytes"], str(4096000 * 1024))
        self.assertEqual(resource.metadata["used_bytes"], str(4096000 * 1024))
        self.assertEqual(resource.metadata["usage_percent"], "50.00")
        self.assertEqual(resource.metadata["swap_used_bytes"], str(1048576 * 1024))

    def test_zero_memtotal_does_not_create_usage_percent(self) -> None:
        resource = memory_to_resource(
            target="tandem",
            meminfo_output="MemTotal: 0 kB\nMemAvailable: 0 kB\n",
        )

        self.assertEqual(resource.metadata["total_bytes"], "0")
        self.assertEqual(resource.metadata["used_bytes"], "0")
        self.assertNotIn("usage_percent", resource.metadata)

    def test_positive_memtotal_still_formats_usage_percent(self) -> None:
        resource = memory_to_resource(
            target="tandem",
            meminfo_output="MemTotal: 100 kB\nMemAvailable: 25 kB\n",
        )

        self.assertEqual(resource.metadata["usage_percent"], "75.00")

    def test_inconsistent_available_does_not_create_negative_fields(self) -> None:
        resource = memory_to_resource(
            target="tandem",
            meminfo_output="MemTotal: 100 kB\nMemAvailable: 200 kB\n",
        )

        self.assertNotIn("used_bytes", resource.metadata)
        self.assertNotIn("usage_percent", resource.metadata)

    def test_output_is_not_mutated(self) -> None:
        output = _meminfo()
        before = copy.deepcopy(output)

        parse_meminfo(output)

        self.assertEqual(output, before)


def _meminfo() -> str:
    return (
        "MemTotal:       8192000 kB\n"
        "MemFree:        1000000 kB\n"
        "MemAvailable:   4096000 kB\n"
        "Buffers:         200000 kB\n"
        "Cached:         3000000 kB\n"
        "SwapTotal:      2097152 kB\n"
        "SwapFree:       1048576 kB\n"
    )


if __name__ == "__main__":
    unittest.main()
