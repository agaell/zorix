from __future__ import annotations

from typing import Protocol, runtime_checkable

from zorix_action_model import ActionExecutionResult, ActionPlan

from .context import ActionContext


@runtime_checkable
class ActionExecutor(Protocol):
    def execute_action(
        self,
        context: ActionContext,
        plan: ActionPlan,
    ) -> ActionExecutionResult:
        ...
