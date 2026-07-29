from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from zorix_linux_adapter.errors import LinuxOutputError
from zorix_linux_adapter.snapshot import (
    SECTION_NAMES,
    STATIC_SNAPSHOT_SCRIPT,
    LinuxSnapshot,
    collect_linux_snapshot,
    parse_linux_snapshot,
)


class FakeSnapshotRunner:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[tuple[str, tuple[str, ...], str | None]] = []

    def run(
        self,
        target: str,
        arguments: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> str:
        self.calls.append((target, tuple(arguments), input_text))
        return self.output


class LinuxSnapshotTest(unittest.TestCase):
    def test_snapshot_model_is_immutable(self) -> None:
        snapshot = parse_linux_snapshot(_valid_snapshot())

        with self.assertRaises(FrozenInstanceError):
            snapshot.hostname_output = "changed"  # type: ignore[misc]

    def test_static_script_contains_all_markers_and_commands(self) -> None:
        for section_name in SECTION_NAMES:
            self.assertIn(
                f'"__ZORIX_SNAPSHOT_V1_BEGIN__:${{section_name}}"',
                STATIC_SNAPSHOT_SCRIPT,
            )
            self.assertIn(
                f'"__ZORIX_SNAPSHOT_V1_END__:${{section_name}}"',
                STATIC_SNAPSHOT_SCRIPT,
            )
            self.assertIn(f"run_section {section_name} ", STATIC_SNAPSHOT_SCRIPT)

        self.assertIn("run_section hostname env LC_ALL=C hostname", STATIC_SNAPSHOT_SCRIPT)
        self.assertIn("run_section kernel env LC_ALL=C uname -r", STATIC_SNAPSHOT_SCRIPT)
        self.assertIn("run_section architecture env LC_ALL=C uname -m", STATIC_SNAPSHOT_SCRIPT)
        self.assertIn("run_section os_release env LC_ALL=C cat /etc/os-release", STATIC_SNAPSHOT_SCRIPT)
        self.assertIn(
            "run_section services env LC_ALL=C systemctl list-units --type=service "
            "--all --no-legend --no-pager --plain --full",
            STATIC_SNAPSHOT_SCRIPT,
        )
        self.assertIn("run_section meminfo env LC_ALL=C cat /proc/meminfo", STATIC_SNAPSHOT_SCRIPT)
        self.assertIn(
            "run_section filesystems env LC_ALL=C df -B1 "
            "--output=source,fstype,size,used,avail,pcent,target",
            STATIC_SNAPSHOT_SCRIPT,
        )
        self.assertIn(
            "run_section sockets env LC_ALL=C ss --no-header --listening --tcp --udp --numeric",
            STATIC_SNAPSHOT_SCRIPT,
        )

    def test_static_script_uses_fixed_safe_constructs(self) -> None:
        self.assertIn('"$@"', STATIC_SNAPSHOT_SCRIPT)
        self.assertNotIn("eval", STATIC_SNAPSHOT_SCRIPT)
        self.assertNotIn("sudo", STATIC_SNAPSHOT_SCRIPT)
        self.assertNotIn("curl", STATIC_SNAPSHOT_SCRIPT)
        self.assertNotIn("wget", STATIC_SNAPSHOT_SCRIPT)
        self.assertNotIn("base64", STATIC_SNAPSHOT_SCRIPT)
        self.assertNotIn("mktemp", STATIC_SNAPSHOT_SCRIPT)

    def test_parse_valid_snapshot(self) -> None:
        snapshot = parse_linux_snapshot(_valid_snapshot())

        self.assertIsInstance(snapshot, LinuxSnapshot)
        self.assertEqual(snapshot.hostname_output, "tandem\n")
        self.assertEqual(snapshot.kernel_output, "6.8.0\n")
        self.assertEqual(snapshot.architecture_output, "x86_64\n")
        self.assertEqual(snapshot.os_release_output, "ID=ubuntu\n")
        self.assertEqual(snapshot.services_output, "nginx.service loaded active running Nginx\n")
        self.assertEqual(snapshot.meminfo_output, "MemTotal: 1 kB\n")
        self.assertEqual(snapshot.filesystems_output, "/dev/vda1 ext4 1 1 0 100% /\n")
        self.assertEqual(snapshot.sockets_output, "tcp LISTEN 0 1 0.0.0.0:80 0.0.0.0:*\n")

    def test_parse_preserves_content_order_and_newlines(self) -> None:
        snapshot = parse_linux_snapshot(
            _valid_snapshot(services="first\n\nsecond\n", sockets="udp line without newline")
        )

        self.assertEqual(snapshot.services_output, "first\n\nsecond\n")
        self.assertEqual(snapshot.sockets_output, "udp line without newline")

    def test_missing_section_raises_output_error(self) -> None:
        output = "".join(
            _section(name, f"{name}\n") for name in SECTION_NAMES if name != "meminfo"
        )

        with self.assertRaisesRegex(LinuxOutputError, "missing section: meminfo"):
            parse_linux_snapshot(output)

    def test_duplicate_begin_raises_output_error(self) -> None:
        output = _valid_snapshot() + _section("services", "duplicate\n")

        with self.assertRaisesRegex(LinuxOutputError, "duplicate section: services"):
            parse_linux_snapshot(output)

    def test_duplicate_end_raises_output_error(self) -> None:
        output = _valid_snapshot() + "__ZORIX_SNAPSHOT_V1_END__:services\n"

        with self.assertRaisesRegex(LinuxOutputError, "unexpected end marker: services"):
            parse_linux_snapshot(output)

    def test_unknown_section_raises_output_error(self) -> None:
        output = "__ZORIX_SNAPSHOT_V1_BEGIN__:unknown\ntext\n__ZORIX_SNAPSHOT_V1_END__:unknown\n"

        with self.assertRaisesRegex(LinuxOutputError, "unknown section: unknown"):
            parse_linux_snapshot(output)

    def test_begin_marker_with_space_inside_section_raises_output_error(self) -> None:
        output = _valid_snapshot(
            services=(
                "ordinary line\n"
                "__ZORIX_SNAPSHOT_V1_BEGIN__:invalid section\n"
                "must not be content\n"
            )
        )

        with self.assertRaisesRegex(LinuxOutputError, "malformed section marker"):
            parse_linux_snapshot(output)

    def test_end_marker_with_space_inside_section_raises_output_error(self) -> None:
        output = _valid_snapshot(
            services=(
                "ordinary line\n"
                "__ZORIX_SNAPSHOT_V1_END__:bad section\n"
                "must not be content\n"
            )
        )

        with self.assertRaisesRegex(LinuxOutputError, "malformed section marker"):
            parse_linux_snapshot(output)

    def test_empty_begin_suffix_raises_output_error(self) -> None:
        output = "__ZORIX_SNAPSHOT_V1_BEGIN__:\n"

        with self.assertRaisesRegex(LinuxOutputError, "empty section marker"):
            parse_linux_snapshot(output)

    def test_empty_end_suffix_raises_output_error(self) -> None:
        output = "__ZORIX_SNAPSHOT_V1_END__:\n"

        with self.assertRaisesRegex(LinuxOutputError, "empty section marker"):
            parse_linux_snapshot(output)

    def test_unknown_well_formed_section_name_raises_output_error(self) -> None:
        output = "__ZORIX_SNAPSHOT_V1_BEGIN__:unknown_section\n"

        with self.assertRaisesRegex(LinuxOutputError, "unknown section: unknown_section"):
            parse_linux_snapshot(output)

    def test_malformed_marker_before_first_section_raises_output_error(self) -> None:
        output = "__ZORIX_SNAPSHOT_V1_BEGIN__:invalid section\n" + _valid_snapshot()

        with self.assertRaisesRegex(LinuxOutputError, "malformed section marker"):
            parse_linux_snapshot(output)

    def test_malformed_marker_after_last_section_raises_output_error(self) -> None:
        output = _valid_snapshot() + "__ZORIX_SNAPSHOT_V1_END__:bad section\n"

        with self.assertRaisesRegex(LinuxOutputError, "malformed section marker"):
            parse_linux_snapshot(output)

    def test_end_without_begin_raises_output_error(self) -> None:
        output = "__ZORIX_SNAPSHOT_V1_END__:sockets\n"

        with self.assertRaisesRegex(LinuxOutputError, "unexpected end marker: sockets"):
            parse_linux_snapshot(output)

    def test_nested_section_raises_output_error(self) -> None:
        output = (
            "__ZORIX_SNAPSHOT_V1_BEGIN__:hostname\n"
            "__ZORIX_SNAPSHOT_V1_BEGIN__:kernel\n"
            "6.8.0\n"
            "__ZORIX_SNAPSHOT_V1_END__:kernel\n"
            "__ZORIX_SNAPSHOT_V1_END__:hostname\n"
        )

        with self.assertRaisesRegex(LinuxOutputError, "nested section: kernel"):
            parse_linux_snapshot(output)

    def test_unclosed_section_raises_output_error(self) -> None:
        output = "__ZORIX_SNAPSHOT_V1_BEGIN__:hostname\nvalue\n"

        with self.assertRaisesRegex(LinuxOutputError, "unclosed section: hostname"):
            parse_linux_snapshot(output)

    def test_non_empty_data_outside_sections_raises_output_error(self) -> None:
        output = "unexpected\n" + _valid_snapshot()

        with self.assertRaisesRegex(LinuxOutputError, "non-empty data outside sections"):
            parse_linux_snapshot(output)

    def test_empty_lines_outside_sections_are_allowed(self) -> None:
        snapshot = parse_linux_snapshot("\n\n" + _valid_snapshot() + "\n")

        self.assertEqual(snapshot.hostname_output, "tandem\n")

    def test_marker_like_text_inside_section_is_allowed_when_not_exact_marker(self) -> None:
        snapshot = parse_linux_snapshot(
            _valid_snapshot(
                services=(
                    "prefix __ZORIX_SNAPSHOT_V1_BEGIN__:kernel\n"
                    "ordinary __ZORIX_SNAPSHOT_V1_END__:bad section\n"
                )
            )
        )

        self.assertEqual(
            snapshot.services_output,
            (
                "prefix __ZORIX_SNAPSHOT_V1_BEGIN__:kernel\n"
                "ordinary __ZORIX_SNAPSHOT_V1_END__:bad section\n"
            ),
        )

    def test_collect_linux_snapshot_calls_runner_once_with_static_script(self) -> None:
        runner = FakeSnapshotRunner(_valid_snapshot())

        snapshot = collect_linux_snapshot(target="tandem", runner=runner)

        self.assertEqual(snapshot.hostname_output, "tandem\n")
        self.assertEqual(runner.calls, [("tandem", ("sh", "-s"), STATIC_SNAPSHOT_SCRIPT)])


def _valid_snapshot(
    *,
    hostname: str = "tandem\n",
    kernel: str = "6.8.0\n",
    architecture: str = "x86_64\n",
    os_release: str = "ID=ubuntu\n",
    services: str = "nginx.service loaded active running Nginx\n",
    meminfo: str = "MemTotal: 1 kB\n",
    filesystems: str = "/dev/vda1 ext4 1 1 0 100% /\n",
    sockets: str = "tcp LISTEN 0 1 0.0.0.0:80 0.0.0.0:*\n",
) -> str:
    return "".join(
        (
            _section("hostname", hostname),
            _section("kernel", kernel),
            _section("architecture", architecture),
            _section("os_release", os_release),
            _section("services", services),
            _section("meminfo", meminfo),
            _section("filesystems", filesystems),
            _section("sockets", sockets),
        )
    )


def _section(name: str, content: str) -> str:
    return (
        f"__ZORIX_SNAPSHOT_V1_BEGIN__:{name}\n"
        f"{content}"
        f"\n__ZORIX_SNAPSHOT_V1_END__:{name}\n"
    )


if __name__ == "__main__":
    unittest.main()
