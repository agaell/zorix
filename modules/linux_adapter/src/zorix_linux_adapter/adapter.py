from __future__ import annotations

from zorix_core_model import Adapter, Resource
from zorix_resource_graph import ResourceRelation
from zorix_topology_api import TopologyContext

from .command import SshCommandRunner, SubprocessSshCommandRunner
from .filesystems import filesystems_to_resources
from .inventory import host_to_resource, services_to_resources, validate_target
from .memory import memory_to_resource
from .sockets import sockets_to_resources
from .topology import host_to_service_relations


_HOSTNAME_ARGUMENTS = ("env", "LC_ALL=C", "hostname")
_KERNEL_ARGUMENTS = ("env", "LC_ALL=C", "uname", "-r")
_ARCHITECTURE_ARGUMENTS = ("env", "LC_ALL=C", "uname", "-m")
_OS_RELEASE_ARGUMENTS = ("env", "LC_ALL=C", "cat", "/etc/os-release")
_SYSTEMD_SERVICES_ARGUMENTS = (
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
_MEMINFO_ARGUMENTS = ("env", "LC_ALL=C", "cat", "/proc/meminfo")
_FILESYSTEMS_ARGUMENTS = (
    "env",
    "LC_ALL=C",
    "df",
    "-B1",
    "--output=source,fstype,size,used,avail,pcent,target",
)
_SOCKETS_ARGUMENTS = (
    "env",
    "LC_ALL=C",
    "ss",
    "--no-header",
    "--listening",
    "--tcp",
    "--udp",
    "--numeric",
)


class LinuxAdapter(Adapter):
    def __init__(
        self,
        target: str,
        runner: SshCommandRunner | None = None,
    ) -> None:
        self.target = validate_target(target)
        self._runner = runner if runner is not None else SubprocessSshCommandRunner()

    def discover(self) -> list[Resource]:
        hostname_output = self._runner.run(self.target, _HOSTNAME_ARGUMENTS)
        kernel_output = self._runner.run(self.target, _KERNEL_ARGUMENTS)
        architecture_output = self._runner.run(self.target, _ARCHITECTURE_ARGUMENTS)
        os_release_output = self._runner.run(self.target, _OS_RELEASE_ARGUMENTS)
        services_output = self._runner.run(self.target, _SYSTEMD_SERVICES_ARGUMENTS)
        meminfo_output = self._runner.run(self.target, _MEMINFO_ARGUMENTS)
        filesystems_output = self._runner.run(self.target, _FILESYSTEMS_ARGUMENTS)
        sockets_output = self._runner.run(self.target, _SOCKETS_ARGUMENTS)

        host = host_to_resource(
            target=self.target,
            hostname_output=hostname_output,
            kernel_output=kernel_output,
            architecture_output=architecture_output,
            os_release_output=os_release_output,
        )
        services = services_to_resources(
            target=self.target,
            systemctl_output=services_output,
        )
        memory = memory_to_resource(
            target=self.target,
            meminfo_output=meminfo_output,
        )
        filesystems = filesystems_to_resources(
            target=self.target,
            filesystems_output=filesystems_output,
        )
        sockets = sockets_to_resources(
            target=self.target,
            sockets_output=sockets_output,
        )

        return [host, *services, memory, *filesystems, *sockets]

    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        return host_to_service_relations(target=self.target, context=context)
