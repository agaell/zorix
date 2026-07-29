from __future__ import annotations

import re

from zorix_action_api import ActionContext
from zorix_action_model import ActionPlan, ActionRequest, ActionRisk, ActionStep
from zorix_core_model import Resource


_SYSTEMD_SERVICE_UNIT_PATTERN = re.compile(r"(?!-)[A-Za-z0-9_.@:-]+\.service\Z")

_OPERATIONS = {
    "service.start": "linux.systemd.start",
    "service.stop": "linux.systemd.stop",
    "service.restart": "linux.systemd.restart",
}

_RISKS = {
    "service.start": ActionRisk.MEDIUM,
    "service.stop": ActionRisk.HIGH,
    "service.restart": ActionRisk.MEDIUM,
}

_VERBS = {
    "service.start": "start",
    "service.stop": "stop",
    "service.restart": "restart",
}

_SUMMARY_VERBS = {
    "service.start": "Start",
    "service.stop": "Stop",
    "service.restart": "Restart",
}


def plan_linux_action(
    *,
    target: str,
    provider: str,
    context: ActionContext,
    request: ActionRequest,
) -> ActionPlan | None:
    if request.action not in _OPERATIONS:
        return None
    if not context.has_resource(request.resource_id):
        return None

    resource = context.resource(request.resource_id)
    unit = _service_unit(target, resource)
    if unit is None:
        return None

    resource_name = _resource_name(resource, unit)
    verb = _VERBS[request.action]

    return ActionPlan(
        source="linux",
        provider=provider,
        request=request,
        resource_name=resource_name,
        operation=_OPERATIONS[request.action],
        risk=_RISKS[request.action],
        requires_confirmation=True,
        summary=f"{_SUMMARY_VERBS[request.action]} systemd service {unit}",
        steps=(
            ActionStep(
                1,
                "linux.service.revalidate",
                "Revalidate the service resource and SSH target",
            ),
            ActionStep(
                2,
                _OPERATIONS[request.action],
                f"Request {verb} of {unit} through the fixed systemd executor",
            ),
            ActionStep(
                3,
                "linux.service.verify",
                "Verify the resulting service state",
            ),
        ),
        metadata={
            "host_id": _host_id(target),
            "ssh_target": target,
            "unit": unit,
        },
    )


def _service_unit(target: str, resource: Resource) -> str | None:
    if resource.type != "service":
        return None
    if not resource.id.startswith(f"linux:service:{target}:"):
        return None
    if resource.metadata.get("host_id") != _host_id(target):
        return None

    unit = resource.metadata.get("unit")
    if not isinstance(unit, str):
        return None

    if unit != unit.strip():
        return None
    if not _valid_service_unit(unit):
        return None
    if resource.id != f"linux:service:{target}:{unit}":
        return None

    return unit


def _valid_service_unit(unit: str) -> bool:
    if not unit:
        return False
    if len(unit) > 256:
        return False
    if any(character.isspace() or ord(character) < 32 for character in unit):
        return False

    return _SYSTEMD_SERVICE_UNIT_PATTERN.fullmatch(unit) is not None


def _resource_name(resource: Resource, unit: str) -> str:
    name = resource.name
    if isinstance(name, str) and name.strip():
        return name.strip()

    return unit


def _host_id(target: str) -> str:
    return f"linux:host:{target}"
