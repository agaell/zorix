from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import unittest

from zorix_action_model import (
    ActionPlan,
    ActionPlanResult,
    ActionPlanStatus,
    ActionRejection,
    ActionRequest,
    ActionRisk,
    ActionStep,
)
from zorix_presentation import ActionPlanConsoleRenderer


class ActionPlanConsoleRendererTest(unittest.TestCase):
    def test_ready_output(self) -> None:
        text = ActionPlanConsoleRenderer().render(_ready_result())

        self.assertEqual(
            text,
            "Action planning: READY\n"
            "Dry run: yes\n"
            "Action: service.restart\n"
            "Resource: tandem.service\n"
            "Resource ID: linux:service:tandem:tandem.service\n"
            "Provider: zorix_linux_adapter.adapter.LinuxAdapter\n"
            "Operation: linux.systemd.restart\n"
            "Risk: MEDIUM\n"
            "Confirmation required: yes\n"
            "Summary: Restart systemd service tandem.service\n"
            "\n"
            "Steps:\n"
            "1. Revalidate the service resource and SSH target\n"
            "2. Request restart of tandem.service through the fixed systemd executor\n"
            "3. Verify the resulting service state\n",
        )

    def test_rejected_output(self) -> None:
        text = ActionPlanConsoleRenderer().render(
            _rejected_result("action.unsupported", "No provider supports service.delete for this resource")
        )

        self.assertEqual(
            text,
            "Action planning: REJECTED\n"
            "Dry run: yes\n"
            "Action: service.delete\n"
            "Resource ID: linux:service:tandem:tandem.service\n"
            "Reason: action.unsupported\n"
            "Message: No provider supports service.delete for this resource\n",
        )

    def test_rejected_resource_not_found(self) -> None:
        text = ActionPlanConsoleRenderer().render(
            _rejected_result("action.resource_not_found", "Resource is not found: missing")
        )

        self.assertIn("Reason: action.resource_not_found\n", text)
        self.assertIn("Message: Resource is not found: missing\n", text)

    def test_risk_confirmation_steps_order_and_no_metadata(self) -> None:
        text = ActionPlanConsoleRenderer().render(_ready_result())

        self.assertIn("Risk: MEDIUM\n", text)
        self.assertIn("Confirmation required: yes\n", text)
        self.assertLess(text.index("1. Revalidate"), text.index("2. Request restart"))
        self.assertLess(text.index("2. Request restart"), text.index("3. Verify"))
        self.assertNotIn("secret", text)

    def test_no_print_final_newline_and_repeated_render(self) -> None:
        renderer = ActionPlanConsoleRenderer()
        result = _ready_result()
        before = (result.status, result.request, result.plan, result.rejection)
        stdout = StringIO()

        with redirect_stdout(stdout):
            first = renderer.render(result)
            second = renderer.render(result)

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertFalse(first.endswith("\n\n"))
        self.assertEqual((result.status, result.request, result.plan, result.rejection), before)


def _request(action: str = "service.restart") -> ActionRequest:
    return ActionRequest(action, "linux:service:tandem:tandem.service")


def _ready_result() -> ActionPlanResult:
    request = _request()
    return ActionPlanResult(
        status=ActionPlanStatus.READY,
        request=request,
        plan=ActionPlan(
            source="linux",
            provider="zorix_linux_adapter.adapter.LinuxAdapter",
            request=request,
            resource_name="tandem.service",
            operation="linux.systemd.restart",
            risk=ActionRisk.MEDIUM,
            requires_confirmation=True,
            summary="Restart systemd service tandem.service",
            steps=(
                ActionStep(1, "linux.service.revalidate", "Revalidate the service resource and SSH target"),
                ActionStep(
                    2,
                    "linux.systemd.restart",
                    "Request restart of tandem.service through the fixed systemd executor",
                ),
                ActionStep(3, "linux.service.verify", "Verify the resulting service state"),
            ),
            metadata={"secret": "hidden"},
        ),
        provider_count=1,
    )


def _rejected_result(code: str, message: str) -> ActionPlanResult:
    return ActionPlanResult(
        status=ActionPlanStatus.REJECTED,
        request=_request("service.delete"),
        rejection=ActionRejection(code, message),
        provider_count=1,
    )


if __name__ == "__main__":
    unittest.main()
