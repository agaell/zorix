from __future__ import annotations

import copy
import unittest

from zorix_action_api import ActionContext, ActionProvider
from zorix_action_engine import ActionEngine
from zorix_action_model import ActionPlanStatus
from zorix_action_model import ActionRequest, ActionRisk
from zorix_core_model import Resource
from zorix_linux_adapter import LinuxAdapter
from zorix_registry import Registry


class FailingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], str | None]] = []

    def run(
        self,
        target: str,
        arguments: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> str:
        self.calls.append((target, tuple(arguments), input_text))
        raise AssertionError("SSH must not be called")


class LinuxActionsTest(unittest.TestCase):
    def test_linux_adapter_is_action_provider(self) -> None:
        self.assertIsInstance(LinuxAdapter("test-host"), ActionProvider)

    def test_service_actions_operation_risk_and_confirmation(self) -> None:
        cases = (
            ("service.start", "linux.systemd.start", ActionRisk.MEDIUM, "Start"),
            ("service.stop", "linux.systemd.stop", ActionRisk.HIGH, "Stop"),
            ("service.restart", "linux.systemd.restart", ActionRisk.MEDIUM, "Restart"),
        )

        for action, operation, risk, summary_verb in cases:
            with self.subTest(action=action):
                plan = _plan(action)
                self.assertEqual(plan.operation, operation)
                self.assertIs(plan.risk, risk)
                self.assertTrue(plan.requires_confirmation)
                self.assertEqual(plan.summary, f"{summary_verb} systemd service tandem.service")
                self.assertEqual(plan.resource_name, "tandem.service")
                self.assertEqual(plan.metadata["host_id"], "linux:host:tandem")
                self.assertEqual(plan.metadata["ssh_target"], "tandem")
                self.assertEqual(plan.metadata["unit"], "tandem.service")

    def test_steps(self) -> None:
        plan = _plan("service.restart")

        self.assertEqual(
            [step.code for step in plan.steps],
            [
                "linux.service.revalidate",
                "linux.systemd.restart",
                "linux.service.verify",
            ],
        )
        self.assertEqual(
            [step.description for step in plan.steps],
            [
                "Revalidate the service resource and SSH target",
                "Request restart of tandem.service through the fixed systemd executor",
                "Verify the resulting service state",
            ],
        )

    def test_unsupported_action_returns_none(self) -> None:
        self.assertIsNone(_maybe_plan("service.delete"))

    def test_real_systemd_service_unit_names_are_supported(self) -> None:
        units = (
            "nginx.service",
            "tandem.service",
            "postgresql@16-main.service",
            "getty@tty1.service",
            "user-runtime-dir@0.service",
            "snap.certbot.renew.service",
        )

        for unit in units:
            with self.subTest(unit=unit):
                resource = _service(unit=unit)
                plan = _adapter().plan_action(
                    ActionContext([resource]),
                    ActionRequest("service.restart", resource.id),
                )

                self.assertIsNotNone(plan)
                self.assertEqual(plan.metadata["unit"], unit)

    def test_unknown_resource_returns_none(self) -> None:
        adapter = _adapter()
        context = ActionContext([_service()])

        plan = adapter.plan_action(
            context,
            ActionRequest("service.restart", "linux:service:tandem:missing.service"),
        )

        self.assertIsNone(plan)

    def test_invalid_resource_shapes_return_none(self) -> None:
        cases = (
            Resource("linux:service:tandem:tandem.service", "container", "tandem.service", "active"),
            _service(resource_id="docker:service:tandem:tandem.service"),
            _service(target="other"),
            _service(host_id="linux:host:other"),
            _service(unit=""),
            _service(unit=" tandem.service", resource_id="linux:service:tandem: tandem.service"),
            _service(unit="tandem.service ", resource_id="linux:service:tandem:tandem.service"),
            _service(unit="tandem.timer", resource_id="linux:service:tandem:tandem.timer"),
            _service(unit="-bad.service", resource_id="linux:service:tandem:-bad.service"),
            _service(unit="bad service.service", resource_id="linux:service:tandem:bad service.service"),
            _service(unit="bad\nservice.service", resource_id="linux:service:tandem:bad\nservice.service"),
            _service(unit="tandem;id.service", resource_id="linux:service:tandem:tandem;id.service"),
            _service(unit="tandem|id.service", resource_id="linux:service:tandem:tandem|id.service"),
            _service(unit="tandem&id.service", resource_id="linux:service:tandem:tandem&id.service"),
            _service(unit="tandem$(id).service", resource_id="linux:service:tandem:tandem$(id).service"),
            _service(unit="tandem`id`.service", resource_id="linux:service:tandem:tandem`id`.service"),
            _service(unit="tandem>file.service", resource_id="linux:service:tandem:tandem>file.service"),
            _service(unit="tandem/file.service", resource_id="linux:service:tandem:tandem/file.service"),
            _service(unit="tandem\\file.service", resource_id="linux:service:tandem:tandem\\file.service"),
            _service(unit="a" * 257 + ".service", resource_id="linux:service:tandem:" + "a" * 257 + ".service"),
            _service(unit="tandem.service", resource_id="linux:service:tandem:other.service"),
        )

        for resource in cases:
            with self.subTest(resource=resource):
                adapter = _adapter()
                context = ActionContext([resource])
                plan = adapter.plan_action(
                    context,
                    ActionRequest("service.restart", resource.id),
                )
                self.assertIsNone(plan)

    def test_rejected_unit_returns_unsupported_from_action_engine_and_does_not_call_runner(self) -> None:
        runner = FailingRunner()
        adapter = LinuxAdapter("tandem", runner)
        registry = Registry()
        registry.register(adapter)
        resource = _service(
            unit="tandem;id.service",
            resource_id="linux:service:tandem:tandem;id.service",
        )

        result = ActionEngine(registry).plan(
            [resource],
            ActionRequest("service.restart", resource.id),
        )

        self.assertIs(result.status, ActionPlanStatus.REJECTED)
        self.assertEqual(result.rejection.code, "action.unsupported")
        self.assertIsNone(result.plan)
        self.assertEqual(runner.calls, [])

    def test_resource_name_falls_back_to_unit(self) -> None:
        resource = _service(name="   ")
        plan = _adapter().plan_action(
            ActionContext([resource]),
            ActionRequest("service.restart", resource.id),
        )

        self.assertEqual(plan.resource_name, "tandem.service")

    def test_runner_context_and_resource_are_not_changed_and_repeated_plan_is_identical(self) -> None:
        runner = FailingRunner()
        adapter = LinuxAdapter("tandem", runner)
        resource = _service()
        before = copy.deepcopy(resource)
        context = ActionContext([resource])
        request = ActionRequest("service.restart", resource.id)

        first = adapter.plan_action(context, request)
        second = adapter.plan_action(context, request)

        self.assertEqual(runner.calls, [])
        self.assertEqual(resource, before)
        self.assertEqual(context.resources(), (resource,))
        self.assertEqual(first, second)


def _adapter() -> LinuxAdapter:
    return LinuxAdapter("tandem", FailingRunner())


def _plan(action: str):
    plan = _maybe_plan(action)
    if plan is None:
        raise AssertionError("expected plan")
    return plan


def _maybe_plan(action: str):
    resource = _service()
    return _adapter().plan_action(ActionContext([resource]), ActionRequest(action, resource.id))


def _service(
    *,
    unit: str = "tandem.service",
    name: str = "tandem.service",
    target: str = "tandem",
    host_id: str = "linux:host:tandem",
    resource_id: str | None = None,
) -> Resource:
    resource_id = resource_id if resource_id is not None else f"linux:service:{target}:{unit}"
    return Resource(
        resource_id,
        "service",
        name,
        "active",
        metadata={
            "host_id": host_id,
            "unit": unit,
            "active_state": "active",
            "sub_state": "running",
        },
    )


if __name__ == "__main__":
    unittest.main()
