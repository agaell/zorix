from __future__ import annotations

import unittest

from zorix_action_model import (
    ActionExecutionRejection,
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionPlan,
    ActionRequest,
    ActionRisk,
    ActionStep,
)
from zorix_presentation import ActionExecutionConsoleRenderer


class ActionExecutionConsoleRendererTest(unittest.TestCase):
    def test_success_output(self) -> None:
        result = ActionExecutionResult(
            ActionExecutionStatus.SUCCESS,
            _request(),
            _plan(),
            "inactive",
            "active",
            True,
            True,
            "executed",
        )

        text = ActionExecutionConsoleRenderer().render(result)

        self.assertTrue(text.endswith("\n"))
        self.assertIn("Action execution: SUCCESS\n", text)
        self.assertIn("Executed: yes\n", text)
        self.assertIn("Confirmed: yes\n", text)
        self.assertIn("Previous state: inactive\n", text)
        self.assertIn("Current state: active\n", text)
        self.assertIn("Changed: yes\n", text)
        self.assertIn("Verified: yes\n", text)

    def test_failed_output_uses_unknown_for_missing_state(self) -> None:
        result = ActionExecutionResult(
            ActionExecutionStatus.FAILED,
            _request(),
            _plan(),
            None,
            None,
            False,
            False,
            "failed",
        )

        text = ActionExecutionConsoleRenderer().render(result)

        self.assertIn("Action execution: FAILED\n", text)
        self.assertIn("Previous state: unknown\n", text)
        self.assertIn("Current state: unknown\n", text)
        self.assertIn("Verified: no\n", text)

    def test_rejected_without_plan(self) -> None:
        result = ActionExecutionResult(
            ActionExecutionStatus.REJECTED,
            _request(),
            None,
            None,
            None,
            False,
            False,
            "rejected",
            rejection=ActionExecutionRejection("action.unsupported", "rejected"),
        )

        text = ActionExecutionConsoleRenderer().render(result)

        self.assertEqual(
            text,
            "\n".join(
                [
                    "Action execution: REJECTED",
                    "Executed: no",
                    "Action: service.restart",
                    "Resource ID: service-1",
                    "Reason: action.unsupported",
                    "Message: rejected",
                ]
            )
            + "\n",
        )

    def test_rejected_with_plan_includes_plan_context(self) -> None:
        result = ActionExecutionResult(
            ActionExecutionStatus.REJECTED,
            _request(),
            _plan(),
            None,
            None,
            False,
            False,
            "confirmation required",
            rejection=ActionExecutionRejection(
                "action.confirmation_required",
                "confirmation required",
            ),
        )

        text = ActionExecutionConsoleRenderer().render(result)

        self.assertIn("Resource: api.service\n", text)
        self.assertIn("Provider: provider.Class\n", text)
        self.assertIn("Operation: linux.systemd.restart\n", text)
        self.assertIn("Risk: MEDIUM\n", text)


def _request() -> ActionRequest:
    return ActionRequest("service.restart", "service-1")


def _plan() -> ActionPlan:
    return ActionPlan(
        "linux",
        "provider.Class",
        _request(),
        "api.service",
        "linux.systemd.restart",
        ActionRisk.MEDIUM,
        True,
        "Restart api.service",
        (ActionStep(1, "step.one", "First step"),),
    )


if __name__ == "__main__":
    unittest.main()
