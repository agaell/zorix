from __future__ import annotations

from collections.abc import Iterable

from zorix_action_api import ActionContext, ActionProvider
from zorix_action_model import (
    ActionPlan,
    ActionPlanResult,
    ActionPlanStatus,
    ActionRejection,
    ActionRequest,
)
from zorix_core_model import Resource
from zorix_registry import Registry

from .errors import AmbiguousActionProviderError, InvalidActionProviderOutputError


class ActionEngine:
    def __init__(self, registry: Registry) -> None:
        if registry is None:
            raise TypeError("registry is required")

        self._registry = registry

    def plan(
        self,
        resources: Iterable[Resource],
        request: ActionRequest,
    ) -> ActionPlanResult:
        if not isinstance(request, ActionRequest):
            raise TypeError("request must be ActionRequest")

        context = ActionContext(resources)
        providers = _action_providers(self._registry.adapters())

        if not context.has_resource(request.resource_id):
            return ActionPlanResult(
                status=ActionPlanStatus.REJECTED,
                request=request,
                rejection=ActionRejection(
                    "action.resource_not_found",
                    f"Resource is not found: {request.resource_id}",
                ),
                provider_count=len(providers),
            )

        plans: list[ActionPlan] = []
        for provider in providers:
            plan = provider.plan_action(context, request)
            if plan is None:
                continue
            if not isinstance(plan, ActionPlan):
                raise InvalidActionProviderOutputError(
                    _provider_name(provider),
                    type(plan).__name__,
                )
            if plan.request != request:
                raise InvalidActionProviderOutputError(
                    _provider_name(provider),
                    "plan request does not match original request",
                )
            if not context.has_resource(plan.request.resource_id):
                raise InvalidActionProviderOutputError(
                    _provider_name(provider),
                    "plan resource is not present in context",
                )

            plans.append(plan)

        if not plans:
            return ActionPlanResult(
                status=ActionPlanStatus.REJECTED,
                request=request,
                rejection=ActionRejection(
                    "action.unsupported",
                    f"No provider supports {request.action} for this resource",
                ),
                provider_count=len(providers),
            )

        if len(plans) > 1:
            raise AmbiguousActionProviderError(
                request.action,
                request.resource_id,
                len(plans),
            )

        return ActionPlanResult(
            status=ActionPlanStatus.READY,
            request=request,
            plan=plans[0],
            provider_count=len(providers),
        )


def _action_providers(adapters: tuple[object, ...]) -> tuple[ActionProvider, ...]:
    return tuple(adapter for adapter in adapters if isinstance(adapter, ActionProvider))


def _provider_name(provider: object) -> str:
    provider_type = type(provider)
    return f"{provider_type.__module__}.{provider_type.__qualname__}"
