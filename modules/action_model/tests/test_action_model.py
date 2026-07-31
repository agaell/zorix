from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from zorix_action_model import (
    ActionExecutionRejection,
    ActionExecutionResult,
    ActionExecutionStatus,
    ActionPlan,
    ActionPlanResult,
    ActionPlanStatus,
    ActionRejection,
    ActionRequest,
    ActionRisk,
    ActionStep,
    risk_rank,
)


class ActionModelTest(unittest.TestCase):
    def test_action_risk_values_and_rank(self) -> None:
        self.assertEqual(ActionRisk.LOW.value, "LOW")
        self.assertEqual(ActionRisk.MEDIUM.value, "MEDIUM")
        self.assertEqual(ActionRisk.HIGH.value, "HIGH")
        self.assertEqual(ActionRisk.CRITICAL.value, "CRITICAL")
        self.assertLess(risk_rank(ActionRisk.LOW), risk_rank(ActionRisk.MEDIUM))
        self.assertLess(risk_rank(ActionRisk.MEDIUM), risk_rank(ActionRisk.HIGH))
        self.assertLess(risk_rank(ActionRisk.HIGH), risk_rank(ActionRisk.CRITICAL))

    def test_action_request_normalization_and_immutability(self) -> None:
        request = ActionRequest(" service.restart ", " resource ")

        self.assertEqual(request.action, "service.restart")
        self.assertEqual(request.resource_id, "resource")
        with self.assertRaises(FrozenInstanceError):
            request.action = "service.stop"  # type: ignore[misc]

    def test_action_request_rejects_empty_strings(self) -> None:
        with self.assertRaises(ValueError):
            ActionRequest("", "resource")
        with self.assertRaises(ValueError):
            ActionRequest("service.restart", "   ")

    def test_action_step_validation(self) -> None:
        step = ActionStep(1, " code ", " description ")

        self.assertEqual(step.code, "code")
        self.assertEqual(step.description, "description")
        for position in (0, -1, True):
            with self.subTest(position=position):
                with self.assertRaises(ValueError):
                    ActionStep(position, "code", "description")  # type: ignore[arg-type]

    def test_action_plan_immutable_identity_and_metadata(self) -> None:
        plan = _plan(metadata={"unit": "api.service"})
        same_without_metadata = _plan(metadata={"unit": "other.service"})

        self.assertEqual(plan.identity, ("linux", "service.restart", "resource"))
        self.assertEqual(plan, same_without_metadata)
        self.assertEqual(hash(plan), hash(same_without_metadata))
        with self.assertRaises(FrozenInstanceError):
            plan.summary = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            plan.metadata["unit"] = "changed"  # type: ignore[index]

    def test_action_plan_requires_tuple_steps_and_sequential_positions(self) -> None:
        with self.assertRaises(ValueError):
            _plan(steps=[])  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            _plan(steps=())
        with self.assertRaises(ValueError):
            _plan(steps=(ActionStep(2, "code", "description"),))

    def test_action_plan_result_ready_invariants(self) -> None:
        result = ActionPlanResult(
            status=ActionPlanStatus.READY,
            request=_request(),
            plan=_plan(),
            provider_count=1,
        )

        self.assertIs(result.status, ActionPlanStatus.READY)
        with self.assertRaises(ValueError):
            ActionPlanResult(ActionPlanStatus.READY, _request())
        with self.assertRaises(ValueError):
            ActionPlanResult(
                ActionPlanStatus.READY,
                _request(),
                plan=_plan(),
                rejection=ActionRejection("code", "message"),
            )

    def test_action_plan_result_rejected_invariants(self) -> None:
        result = ActionPlanResult(
            status=ActionPlanStatus.REJECTED,
            request=_request(),
            rejection=ActionRejection(" action.unsupported ", " unsupported "),
        )

        self.assertEqual(result.rejection.code, "action.unsupported")
        self.assertEqual(result.rejection.message, "unsupported")
        with self.assertRaises(ValueError):
            ActionPlanResult(ActionPlanStatus.REJECTED, _request())
        with self.assertRaises(ValueError):
            ActionPlanResult(
                ActionPlanStatus.REJECTED,
                _request(),
                plan=_plan(),
                rejection=ActionRejection("code", "message"),
            )

    def test_invalid_provider_count(self) -> None:
        for provider_count in (-1, True):
            with self.subTest(provider_count=provider_count):
                with self.assertRaises(ValueError):
                    ActionPlanResult(
                        ActionPlanStatus.REJECTED,
                        _request(),
                        rejection=ActionRejection("code", "message"),
                        provider_count=provider_count,  # type: ignore[arg-type]
                    )

    def test_action_execution_result_success_invariants_and_metadata(self) -> None:
        metadata = {"unit": "api.service"}
        result = ActionExecutionResult(
            ActionExecutionStatus.SUCCESS,
            _request(),
            _plan(),
            " inactive ",
            " active ",
            True,
            True,
            " executed ",
            metadata=metadata,
        )
        metadata["unit"] = "changed.service"

        self.assertEqual(result.previous_state, "inactive")
        self.assertEqual(result.current_state, "active")
        self.assertEqual(result.message, "executed")
        self.assertEqual(result.metadata["unit"], "api.service")
        with self.assertRaises(TypeError):
            result.metadata["unit"] = "other.service"  # type: ignore[index]
        with self.assertRaises(ValueError):
            ActionExecutionResult(
                ActionExecutionStatus.SUCCESS,
                _request(),
                _plan(),
                None,
                None,
                False,
                False,
                "bad",
            )

    def test_action_execution_result_failed_and_rejected_invariants(self) -> None:
        failed = ActionExecutionResult(
            ActionExecutionStatus.FAILED,
            _request(),
            _plan(),
            "active",
            "failed",
            False,
            False,
            "failed",
        )
        self.assertIs(failed.status, ActionExecutionStatus.FAILED)

        rejected = ActionExecutionResult(
            ActionExecutionStatus.REJECTED,
            _request(),
            None,
            None,
            None,
            False,
            False,
            "rejected",
            rejection=ActionExecutionRejection(" action.unsupported ", " unsupported "),
        )
        self.assertEqual(rejected.rejection.code, "action.unsupported")
        self.assertEqual(rejected.rejection.message, "unsupported")
        with self.assertRaises(ValueError):
            ActionExecutionResult(
                ActionExecutionStatus.REJECTED,
                _request(),
                None,
                None,
                None,
                True,
                False,
                "bad",
                rejection=ActionExecutionRejection("code", "message"),
            )


def _request() -> ActionRequest:
    return ActionRequest("service.restart", "resource")


def _plan(
    *,
    steps: tuple[ActionStep, ...] = (
        ActionStep(1, "step.one", "First step"),
    ),
    metadata: dict[str, str] | None = None,
) -> ActionPlan:
    return ActionPlan(
        source="linux",
        provider="provider.Class",
        request=_request(),
        resource_name="resource",
        operation="linux.systemd.restart",
        risk=ActionRisk.MEDIUM,
        requires_confirmation=True,
        summary="Restart service",
        steps=steps,
        metadata={} if metadata is None else metadata,
    )


if __name__ == "__main__":
    unittest.main()
