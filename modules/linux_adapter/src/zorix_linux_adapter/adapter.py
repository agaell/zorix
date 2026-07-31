from __future__ import annotations

from zorix_action_api import ActionContext
from zorix_action_model import ActionExecutionResult, ActionPlan, ActionRequest
from zorix_core_model import Adapter, Resource
from zorix_health_api import HealthContext
from zorix_health_model import HealthFinding
from zorix_resource_graph import ResourceRelation
from zorix_topology_api import TopologyContext

from .command import SshCommandRunner, SubprocessSshCommandRunner
from .action_execution import execute_linux_action
from .actions import plan_linux_action
from .filesystems import filesystems_to_resources
from .health import evaluate_linux_health
from .inventory import host_to_resource, services_to_resources, validate_target
from .memory import memory_to_resource
from .snapshot import collect_linux_snapshot
from .sockets import sockets_to_resources
from .topology import host_to_service_relations


class LinuxAdapter(Adapter):
    def __init__(
        self,
        target: str,
        runner: SshCommandRunner | None = None,
    ) -> None:
        self.target = validate_target(target)
        self._runner = runner if runner is not None else SubprocessSshCommandRunner()

    def discover(self) -> list[Resource]:
        snapshot = collect_linux_snapshot(target=self.target, runner=self._runner)

        host = host_to_resource(
            target=self.target,
            hostname_output=snapshot.hostname_output,
            kernel_output=snapshot.kernel_output,
            architecture_output=snapshot.architecture_output,
            os_release_output=snapshot.os_release_output,
        )
        services = services_to_resources(
            target=self.target,
            systemctl_output=snapshot.services_output,
        )
        memory = memory_to_resource(
            target=self.target,
            meminfo_output=snapshot.meminfo_output,
        )
        filesystems = filesystems_to_resources(
            target=self.target,
            filesystems_output=snapshot.filesystems_output,
        )
        sockets = sockets_to_resources(
            target=self.target,
            sockets_output=snapshot.sockets_output,
        )

        return [host, *services, memory, *filesystems, *sockets]

    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        return host_to_service_relations(target=self.target, context=context)

    def evaluate_health(self, context: HealthContext) -> list[HealthFinding]:
        return evaluate_linux_health(target=self.target, context=context)

    def plan_action(
        self,
        context: ActionContext,
        request: ActionRequest,
    ) -> ActionPlan | None:
        return plan_linux_action(
            target=self.target,
            provider=_class_name(self),
            context=context,
            request=request,
        )

    def execute_action(
        self,
        context: ActionContext,
        plan: ActionPlan,
    ) -> ActionExecutionResult:
        return execute_linux_action(
            target=self.target,
            provider=_class_name(self),
            runner=self._runner,
            context=context,
            plan=plan,
        )


def _class_name(value: object) -> str:
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"
