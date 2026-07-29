from __future__ import annotations

from collections.abc import Iterable

from zorix_core_model import Resource
from zorix_health_api import HealthContext, HealthProvider
from zorix_health_model import HealthFinding, health_level_for_findings
from zorix_registry import Registry

from .errors import InvalidHealthProviderOutputError
from .result import HealthProviderError, HealthResult, HealthStatus


class HealthEngine:
    def __init__(self, registry: Registry) -> None:
        if registry is None:
            raise TypeError("registry is required")

        self._registry = registry

    def evaluate(
        self,
        resources: Iterable[Resource],
        *,
        continue_on_error: bool = False,
    ) -> HealthResult:
        context = HealthContext(resources)
        providers = _health_providers(self._registry.adapters())
        findings: list[HealthFinding] = []
        finding_identities: set[tuple[str, str, str]] = set()
        errors: list[HealthProviderError] = []
        successful_provider_count = 0

        for provider in providers:
            try:
                provider_findings = _validated_provider_findings(provider, context)
                for finding in provider_findings:
                    if finding.identity in finding_identities:
                        continue

                    findings.append(finding)
                    finding_identities.add(finding.identity)

                successful_provider_count += 1
            except Exception as exc:
                if not continue_on_error:
                    raise

                errors.append(_provider_error(provider, exc))

        finding_tuple = tuple(findings)
        return HealthResult(
            status=_health_status(len(providers), successful_provider_count),
            level=health_level_for_findings(finding_tuple),
            findings=finding_tuple,
            errors=tuple(errors),
            provider_count=len(providers),
            successful_provider_count=successful_provider_count,
            resource_count=len(context),
        )


def _validated_provider_findings(
    provider: HealthProvider,
    context: HealthContext,
) -> list[HealthFinding]:
    findings = provider.evaluate_health(context)
    if not isinstance(findings, list):
        raise InvalidHealthProviderOutputError(
            _provider_name(provider),
            type(findings).__name__,
        )

    for finding in findings:
        if not isinstance(finding, HealthFinding):
            raise InvalidHealthProviderOutputError(
                _provider_name(provider),
                type(finding).__name__,
            )

    return findings


def _health_providers(adapters: tuple[object, ...]) -> tuple[HealthProvider, ...]:
    return tuple(adapter for adapter in adapters if isinstance(adapter, HealthProvider))


def _provider_error(provider: object, exc: Exception) -> HealthProviderError:
    return HealthProviderError(
        provider=_provider_name(provider),
        error_type=type(exc).__name__,
        message=str(exc),
    )


def _provider_name(provider: object) -> str:
    provider_type = type(provider)
    return f"{provider_type.__module__}.{provider_type.__qualname__}"


def _health_status(
    provider_count: int,
    successful_provider_count: int,
) -> HealthStatus:
    failed_provider_count = provider_count - successful_provider_count

    if provider_count == 0:
        return HealthStatus.SUCCESS
    if failed_provider_count == 0:
        return HealthStatus.SUCCESS
    if successful_provider_count > 0:
        return HealthStatus.PARTIAL
    return HealthStatus.FAILED
