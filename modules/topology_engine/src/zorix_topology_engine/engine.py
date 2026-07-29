from __future__ import annotations

from collections.abc import Iterable

from zorix_core_model import Resource
from zorix_registry import Registry
from zorix_resource_graph import ResourceGraphBuilder
from zorix_topology_api import TopologyContext, TopologyProvider

from .errors import InvalidTopologyProviderOutputError
from .models import TopologyProviderError, TopologyResult, TopologyStatus


class TopologyEngine:
    def __init__(self, registry: Registry) -> None:
        if registry is None:
            raise TypeError("registry is required")

        self._registry = registry

    def build(
        self,
        resources: Iterable[Resource],
        *,
        continue_on_error: bool = False,
    ) -> TopologyResult:
        context = TopologyContext(resources)
        builder = ResourceGraphBuilder()
        builder.add_resources(context.resources())

        providers = _topology_providers(self._registry.adapters())
        successful_provider_count = 0
        errors: list[TopologyProviderError] = []

        for provider in providers:
            try:
                relations = provider.discover_relations(context)
                if not isinstance(relations, list):
                    raise InvalidTopologyProviderOutputError(
                        _provider_name(provider),
                        type(relations).__name__,
                    )

                builder.add_relations(relations)
                successful_provider_count += 1
            except Exception as exc:
                if not continue_on_error:
                    raise

                errors.append(_provider_error(provider, exc))

        graph = builder.build()

        return TopologyResult(
            status=_topology_status(len(providers), successful_provider_count),
            graph=graph,
            errors=tuple(errors),
            provider_count=len(providers),
            successful_provider_count=successful_provider_count,
        )


def _topology_providers(adapters: tuple[object, ...]) -> tuple[TopologyProvider, ...]:
    return tuple(
        adapter
        for adapter in adapters
        if isinstance(adapter, TopologyProvider)
    )


def _provider_error(provider: object, exc: Exception) -> TopologyProviderError:
    return TopologyProviderError(
        provider=_provider_name(provider),
        error_type=type(exc).__name__,
        message=str(exc),
    )


def _provider_name(provider: object) -> str:
    provider_type = type(provider)
    return f"{provider_type.__module__}.{provider_type.__qualname__}"


def _topology_status(
    provider_count: int,
    successful_provider_count: int,
) -> TopologyStatus:
    failed_provider_count = provider_count - successful_provider_count

    if provider_count == 0:
        return TopologyStatus.SUCCESS

    if failed_provider_count == 0:
        return TopologyStatus.SUCCESS

    if successful_provider_count > 0:
        return TopologyStatus.PARTIAL

    return TopologyStatus.FAILED
