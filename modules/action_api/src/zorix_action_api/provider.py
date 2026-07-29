from __future__ import annotations

from typing import Protocol, runtime_checkable

from zorix_action_model import ActionPlan, ActionRequest

from .context import ActionContext


@runtime_checkable
class ActionProvider(Protocol):
    def plan_action(
        self,
        context: ActionContext,
        request: ActionRequest,
    ) -> ActionPlan | None:
        ...
