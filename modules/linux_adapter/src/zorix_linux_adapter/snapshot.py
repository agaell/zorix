from __future__ import annotations

from dataclasses import dataclass

from .command import SshCommandRunner
from .errors import LinuxOutputError


SECTION_NAMES = (
    "hostname",
    "kernel",
    "architecture",
    "os_release",
    "services",
    "meminfo",
    "filesystems",
    "sockets",
)

_BEGIN_PREFIX = "__ZORIX_SNAPSHOT_V1_BEGIN__:"
_END_PREFIX = "__ZORIX_SNAPSHOT_V1_END__:"
_SNAPSHOT_ARGUMENTS = ("sh", "-s")

# This static production script has no user commands or target interpolation.
STATIC_SNAPSHOT_SCRIPT = """\
run_section() {
    section_name="$1"
    shift
    printf '%s\\n' "__ZORIX_SNAPSHOT_V1_BEGIN__:${section_name}"
    "$@"
    status=$?
    printf '\\n%s\\n' "__ZORIX_SNAPSHOT_V1_END__:${section_name}"
    if [ "$status" -ne 0 ]; then
        printf '%s\\n' "Zorix snapshot command failed: ${section_name}" >&2
        exit "$status"
    fi
}

run_section hostname env LC_ALL=C hostname
run_section kernel env LC_ALL=C uname -r
run_section architecture env LC_ALL=C uname -m
run_section os_release env LC_ALL=C cat /etc/os-release
run_section services env LC_ALL=C systemctl list-units --type=service --all --no-legend --no-pager --plain --full
run_section meminfo env LC_ALL=C cat /proc/meminfo
run_section filesystems env LC_ALL=C df -B1 --output=source,fstype,size,used,avail,pcent,target
run_section sockets env LC_ALL=C ss --no-header --listening --tcp --udp --numeric
"""


@dataclass(frozen=True)
class LinuxSnapshot:
    hostname_output: str
    kernel_output: str
    architecture_output: str
    os_release_output: str
    services_output: str
    meminfo_output: str
    filesystems_output: str
    sockets_output: str


def collect_linux_snapshot(*, target: str, runner: SshCommandRunner) -> LinuxSnapshot:
    output = runner.run(
        target,
        _SNAPSHOT_ARGUMENTS,
        input_text=STATIC_SNAPSHOT_SCRIPT,
    )
    return parse_linux_snapshot(output)


def parse_linux_snapshot(output: str) -> LinuxSnapshot:
    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for raw_line in output.splitlines(keepends=True):
        line = _line_without_newline(raw_line)
        begin_section = _section_from_marker(line, _BEGIN_PREFIX)
        end_section = _section_from_marker(line, _END_PREFIX)

        if begin_section is not None:
            _validate_section_name(begin_section)
            if current_section is not None:
                raise LinuxOutputError(
                    f"Linux snapshot contains nested section: {begin_section}"
                )
            if begin_section in sections:
                raise LinuxOutputError(
                    f"Linux snapshot contains duplicate section: {begin_section}"
                )
            current_section = begin_section
            current_lines = []
            continue

        if end_section is not None:
            _validate_section_name(end_section)
            if current_section is None:
                raise LinuxOutputError(
                    f"Linux snapshot contains an unexpected end marker: {end_section}"
                )
            if end_section != current_section:
                raise LinuxOutputError(
                    f"Linux snapshot contains an unexpected end marker: {end_section}"
                )
            sections[current_section] = _remove_artificial_separator_newline(
                "".join(current_lines)
            )
            current_section = None
            current_lines = []
            continue

        if current_section is None:
            if line:
                raise LinuxOutputError(
                    "Linux snapshot contains non-empty data outside sections"
                )
            continue

        current_lines.append(raw_line)

    if current_section is not None:
        raise LinuxOutputError(f"Linux snapshot contains unclosed section: {current_section}")

    for section_name in SECTION_NAMES:
        if section_name not in sections:
            raise LinuxOutputError(f"Linux snapshot is missing section: {section_name}")

    return LinuxSnapshot(
        hostname_output=sections["hostname"],
        kernel_output=sections["kernel"],
        architecture_output=sections["architecture"],
        os_release_output=sections["os_release"],
        services_output=sections["services"],
        meminfo_output=sections["meminfo"],
        filesystems_output=sections["filesystems"],
        sockets_output=sections["sockets"],
    )


def _line_without_newline(line: str) -> str:
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line


def _section_from_marker(line: str, prefix: str) -> str | None:
    if not line.startswith(prefix):
        return None
    return line.removeprefix(prefix)


def _validate_section_name(section_name: str) -> None:
    if not section_name:
        raise LinuxOutputError("Linux snapshot contains empty section marker")
    if any(character.isspace() for character in section_name):
        raise LinuxOutputError(
            f"Linux snapshot contains malformed section marker: {section_name}"
        )
    if section_name not in SECTION_NAMES:
        raise LinuxOutputError(f"Linux snapshot contains unknown section: {section_name}")


def _remove_artificial_separator_newline(content: str) -> str:
    if content.endswith("\n"):
        return content[:-1]
    return content
