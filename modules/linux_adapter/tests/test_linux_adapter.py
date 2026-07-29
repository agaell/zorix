from __future__ import annotations

import unittest
from unittest.mock import patch

from zorix_core_model import Resource
from zorix_linux_adapter import LinuxAdapter, LinuxOutputError


HOSTNAME_ARGS = ("env", "LC_ALL=C", "hostname")
KERNEL_ARGS = ("env", "LC_ALL=C", "uname", "-r")
ARCH_ARGS = ("env", "LC_ALL=C", "uname", "-m")
OS_RELEASE_ARGS = ("env", "LC_ALL=C", "cat", "/etc/os-release")
SYSTEMCTL_ARGS = (
    "env",
    "LC_ALL=C",
    "systemctl",
    "list-units",
    "--type=service",
    "--all",
    "--no-legend",
    "--no-pager",
    "--plain",
    "--full",
)
MEMINFO_ARGS = ("env", "LC_ALL=C", "cat", "/proc/meminfo")
FILESYSTEMS_ARGS = (
    "env",
    "LC_ALL=C",
    "df",
    "-B1",
    "--output=source,fstype,size,used,avail,pcent,target",
)
SOCKETS_ARGS = (
    "env",
    "LC_ALL=C",
    "ss",
    "--no-header",
    "--listening",
    "--tcp",
    "--udp",
    "--numeric",
)


class FakeSshCommandRunner:
    def __init__(self, *outputs: str | BaseException) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def run(self, target: str, arguments: tuple[str, ...]) -> str:
        self.calls.append((target, tuple(arguments)))
        if not self._outputs:
            raise AssertionError("unexpected SSH command")

        output = self._outputs.pop(0)
        if isinstance(output, BaseException):
            raise output

        return output


class FalseySshCommandRunner(FakeSshCommandRunner):
    def __bool__(self) -> bool:
        return False


class LinuxAdapterTest(unittest.TestCase):
    def test_discover_calls_commands_in_exact_order(self) -> None:
        runner = _runner()

        LinuxAdapter("tandem", runner).discover()

        self.assertEqual(
            runner.calls,
            [
                ("tandem", HOSTNAME_ARGS),
                ("tandem", KERNEL_ARGS),
                ("tandem", ARCH_ARGS),
                ("tandem", OS_RELEASE_ARGS),
                ("tandem", SYSTEMCTL_ARGS),
                ("tandem", MEMINFO_ARGS),
                ("tandem", FILESYSTEMS_ARGS),
                ("tandem", SOCKETS_ARGS),
            ],
        )

    def test_host_resource_mapping(self) -> None:
        resources = LinuxAdapter("tandem", _runner()).discover()
        host = resources[0]

        self.assertIsInstance(host, Resource)
        self.assertEqual(host.id, "linux:host:tandem")
        self.assertEqual(host.type, "host")
        self.assertEqual(host.name, "tandem-server")
        self.assertEqual(host.state, "reachable")
        self.assertEqual(host.labels, {})
        self.assertEqual(host.metadata["ssh_target"], "tandem")
        self.assertEqual(host.metadata["kernel"], "6.8.0")
        self.assertEqual(host.metadata["architecture"], "x86_64")
        self.assertEqual(host.metadata["os_id"], "ubuntu")
        self.assertEqual(host.metadata["os_name"], "Ubuntu 24.04 LTS")
        self.assertEqual(host.metadata["os_version"], "24.04")

    def test_empty_hostname_uses_target_as_name(self) -> None:
        runner = _runner(hostname="\n")

        host = LinuxAdapter("tandem", runner).discover()[0]

        self.assertEqual(host.name, "tandem")

    def test_service_resource_mapping_and_order(self) -> None:
        resources = LinuxAdapter("tandem", _runner()).discover()
        services = resources[1:]

        self.assertEqual([service.name for service in services[:2]], ["nginx.service", "postgresql.service"])
        self.assertEqual(services[0].id, "linux:service:tandem:nginx.service")
        self.assertEqual(services[0].type, "service")
        self.assertEqual(services[0].state, "active")
        self.assertEqual(services[0].labels, {})
        self.assertEqual(services[0].metadata["host_id"], "linux:host:tandem")
        self.assertEqual(services[0].metadata["unit"], "nginx.service")
        self.assertEqual(services[0].metadata["load_state"], "loaded")
        self.assertEqual(services[0].metadata["active_state"], "active")
        self.assertEqual(services[0].metadata["sub_state"], "running")
        self.assertEqual(services[0].metadata["description"], "A web server")
        self.assertEqual(services[1].state, "inactive")

    def test_empty_services_returns_only_host(self) -> None:
        resources = LinuxAdapter("tandem", _runner(services="")).discover()

        self.assertEqual([resource.type for resource in resources], ["host", "memory", "filesystem", "socket"])
        self.assertEqual(resources[0].type, "host")

    def test_duplicate_services_are_removed(self) -> None:
        resources = LinuxAdapter(
            "tandem",
            _runner(
                services=(
                    "nginx.service loaded active running First\n"
                    "nginx.service loaded failed failed Second\n"
                )
            ),
        ).discover()

        self.assertEqual(resources[1].type, "service")
        self.assertEqual(resources[1].state, "active")
        self.assertEqual(resources[1].metadata["description"], "First")

    def test_new_resource_order(self) -> None:
        resources = LinuxAdapter("tandem", _runner()).discover()

        self.assertEqual(
            [resource.type for resource in resources],
            ["host", "service", "service", "memory", "filesystem", "socket"],
        )

    def test_empty_df_and_ss_do_not_break_scan(self) -> None:
        resources = LinuxAdapter(
            "tandem",
            _runner(filesystems="", sockets=""),
        ).discover()

        self.assertEqual([resource.type for resource in resources], ["host", "service", "service", "memory"])

    def test_malformed_filesystem_and_socket_rows_are_skipped(self) -> None:
        resources = LinuxAdapter(
            "tandem",
            _runner(filesystems="bad\n", sockets="bad\n"),
        ).discover()

        self.assertEqual([resource.type for resource in resources], ["host", "service", "service", "memory"])

    def test_invalid_meminfo_raises_output_error(self) -> None:
        with self.assertRaises(LinuxOutputError):
            LinuxAdapter("tandem", _runner(meminfo="MemFree: 1 kB\n")).discover()

    def test_new_command_error_is_propagated(self) -> None:
        error = RuntimeError("df failed")
        runner = FakeSshCommandRunner(*_outputs()[:6], error)

        with self.assertRaises(RuntimeError) as context:
            LinuxAdapter("tandem", runner).discover()

        self.assertIs(context.exception, error)

    def test_command_error_is_propagated(self) -> None:
        error = RuntimeError("ssh failed")
        runner = FakeSshCommandRunner(error)

        with self.assertRaises(RuntimeError) as context:
            LinuxAdapter("tandem", runner).discover()

        self.assertIs(context.exception, error)

    def test_repeated_discover_with_same_outputs_returns_equal_resources(self) -> None:
        runner = FakeSshCommandRunner(*_outputs(), *_outputs())
        adapter = LinuxAdapter("tandem", runner)

        first = adapter.discover()
        second = adapter.discover()

        self.assertEqual(first, second)

    def test_falsey_runner_is_not_replaced_with_default_runner(self) -> None:
        runner = FalseySshCommandRunner(*_outputs())

        with patch("zorix_linux_adapter.adapter.SubprocessSshCommandRunner") as default_runner:
            resources = LinuxAdapter("tandem", runner).discover()

        self.assertEqual(len(resources), 6)
        default_runner.assert_not_called()


def _runner(
    *,
    hostname: str = "tandem-server\n",
    services: str | None = None,
    meminfo: str | None = None,
    filesystems: str | None = None,
    sockets: str | None = None,
) -> FakeSshCommandRunner:
    return FakeSshCommandRunner(
        *_outputs(
            hostname=hostname,
            services=services,
            meminfo=meminfo,
            filesystems=filesystems,
            sockets=sockets,
        ),
    )


def _outputs(
    *,
    hostname: str = "tandem-server\n",
    services: str | None = None,
    meminfo: str | None = None,
    filesystems: str | None = None,
    sockets: str | None = None,
) -> tuple[str, ...]:
    if services is None:
        services = (
            "nginx.service loaded active running A web server\n"
            "postgresql.service loaded inactive dead PostgreSQL\n"
        )
    if meminfo is None:
        meminfo = "MemTotal: 8192000 kB\nMemAvailable: 4096000 kB\n"
    if filesystems is None:
        filesystems = "/dev/vda1 ext4 100 20 80 20% /\n"
    if sockets is None:
        sockets = "tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:*\n"

    return (
        hostname,
        "6.8.0\n",
        "x86_64\n",
        'ID=ubuntu\nNAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04 LTS"\nVERSION_ID="24.04"\n',
        services,
        meminfo,
        filesystems,
        sockets,
    )


if __name__ == "__main__":
    unittest.main()
