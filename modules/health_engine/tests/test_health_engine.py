from __future__ import annotations

import copy
from collections.abc import Iterable, Iterator
import unittest

from zorix_core_model import Adapter, Resource
from zorix_health_api import HealthContext
from zorix_health_engine import (
    HealthEngine,
    HealthProviderError,
    HealthResult,
    HealthStatus,
    InvalidHealthProviderOutputError,
)
from zorix_health_model import HealthFinding, HealthLevel, HealthSeverity
from zorix_registry import Registry


class StaticProvider(Adapter):
    def __init__(self, findings: list[HealthFinding]) -> None:
        self.findings = findings
        self.contexts: list[HealthContext] = []

    def discover(self) -> list[Resource]:
        return []

    def evaluate_health(self, context: HealthContext) -> list[HealthFinding]:
        self.contexts.append(context)
        return list(self.findings)


class SecondStaticProvider(StaticProvider):
    pass


class FailingProvider(Adapter):
    def discover(self) -> list[Resource]:
        return []

    def evaluate_health(self, context: HealthContext) -> list[HealthFinding]:
        raise RuntimeError("provider failed")


class SecondFailingProvider(FailingProvider):
    pass


class InvalidOutputProvider(Adapter):
    def __init__(self, output: object) -> None:
        self.output = output

    def discover(self) -> list[Resource]:
        return []

    def evaluate_health(self, context: HealthContext) -> object:
        return self.output


class NotHealthAdapter(Adapter):
    def discover(self) -> list[Resource]:
        return []


class CountingResources:
    def __init__(self, resources: list[Resource]) -> None:
        self.resources = resources
        self.iteration_count = 0

    def __iter__(self) -> Iterator[Resource]:
        self.iteration_count += 1
        return iter(self.resources)


class HealthEngineTest(unittest.TestCase):
    def test_no_providers(self) -> None:
        result = HealthEngine(Registry()).evaluate([_resource("r1")])

        self.assertIs(result.status, HealthStatus.SUCCESS)
        self.assertIs(result.level, HealthLevel.HEALTHY)
        self.assertEqual(result.findings, ())
        self.assertEqual(result.provider_count, 0)
        self.assertEqual(result.resource_count, 1)

    def test_one_successful_provider(self) -> None:
        provider = StaticProvider([_finding("r1", HealthSeverity.WARNING)])
        registry = _registry(provider)

        result = HealthEngine(registry).evaluate([_resource("r1")])

        self.assertIs(result.status, HealthStatus.SUCCESS)
        self.assertIs(result.level, HealthLevel.WARNING)
        self.assertEqual(result.finding_count, 1)
        self.assertEqual(result.successful_provider_count, 1)

    def test_multiple_providers_and_order(self) -> None:
        first = _finding("r1", HealthSeverity.INFO, code="first")
        second = _finding("r2", HealthSeverity.WARNING, code="second")
        result = HealthEngine(_registry(StaticProvider([first]), SecondStaticProvider([second]))).evaluate(
            [_resource("r1"), _resource("r2")]
        )

        self.assertEqual(result.findings, (first, second))
        self.assertEqual(result.provider_count, 2)

    def test_finding_order_is_preserved(self) -> None:
        first = _finding("r1", HealthSeverity.INFO, code="first")
        second = _finding("r2", HealthSeverity.INFO, code="second")

        result = HealthEngine(_registry(StaticProvider([first, second]))).evaluate([])

        self.assertEqual(result.findings, (first, second))

    def test_deduplication_preserves_first(self) -> None:
        first = _finding("r1", HealthSeverity.WARNING, message="first")
        second = _finding("r1", HealthSeverity.WARNING, message="second")

        result = HealthEngine(_registry(StaticProvider([first, second]))).evaluate([])

        self.assertEqual(result.findings, (first,))

    def test_levels(self) -> None:
        self.assertIs(HealthEngine(_registry(StaticProvider([]))).evaluate([]).level, HealthLevel.HEALTHY)
        self.assertIs(
            HealthEngine(_registry(StaticProvider([_finding("r1", HealthSeverity.INFO)]))).evaluate([]).level,
            HealthLevel.HEALTHY,
        )
        self.assertIs(
            HealthEngine(_registry(StaticProvider([_finding("r1", HealthSeverity.WARNING)]))).evaluate([]).level,
            HealthLevel.WARNING,
        )
        self.assertIs(
            HealthEngine(_registry(StaticProvider([_finding("r1", HealthSeverity.CRITICAL)]))).evaluate([]).level,
            HealthLevel.CRITICAL,
        )

    def test_fail_fast_exception_is_propagated(self) -> None:
        with self.assertRaises(RuntimeError):
            HealthEngine(_registry(FailingProvider())).evaluate([])

    def test_continue_on_error_partial(self) -> None:
        result = HealthEngine(
            _registry(StaticProvider([_finding("r1", HealthSeverity.INFO)]), FailingProvider())
        ).evaluate([], continue_on_error=True)

        self.assertIs(result.status, HealthStatus.PARTIAL)
        self.assertEqual(result.successful_provider_count, 1)
        self.assertEqual(result.failed_provider_count, 1)
        self.assertIsInstance(result.errors[0], HealthProviderError)
        self.assertEqual(result.errors[0].error_type, "RuntimeError")

    def test_all_failed(self) -> None:
        result = HealthEngine(_registry(FailingProvider(), SecondFailingProvider())).evaluate(
            [],
            continue_on_error=True,
        )

        self.assertIs(result.status, HealthStatus.FAILED)
        self.assertEqual(result.successful_provider_count, 0)
        self.assertEqual(result.failed_provider_count, 2)

    def test_invalid_output_is_rejected(self) -> None:
        for output in (None, tuple(), (finding for finding in ())):
            with self.subTest(output=type(output).__name__):
                with self.assertRaises(InvalidHealthProviderOutputError):
                    HealthEngine(_registry(InvalidOutputProvider(output))).evaluate([])

    def test_invalid_item_is_rejected(self) -> None:
        with self.assertRaises(InvalidHealthProviderOutputError):
            HealthEngine(_registry(InvalidOutputProvider(["not finding"]))).evaluate([])

    def test_atomic_batch_on_invalid_item_in_continue_mode(self) -> None:
        good = _finding("r1", HealthSeverity.WARNING)
        result = HealthEngine(_registry(InvalidOutputProvider([good, "bad"]))).evaluate(
            [],
            continue_on_error=True,
        )

        self.assertEqual(result.findings, ())
        self.assertIs(result.status, HealthStatus.FAILED)
        self.assertEqual(len(result.errors), 1)

    def test_repeated_evaluate_uses_current_registry(self) -> None:
        registry = Registry()
        engine = HealthEngine(registry)

        first = engine.evaluate([])
        registry.register(StaticProvider([_finding("r1", HealthSeverity.INFO)]))
        second = engine.evaluate([])

        self.assertEqual(first.provider_count, 0)
        self.assertEqual(second.provider_count, 1)

    def test_non_health_adapters_are_ignored(self) -> None:
        result = HealthEngine(_registry(NotHealthAdapter())).evaluate([])

        self.assertEqual(result.provider_count, 0)

    def test_resources_are_not_changed(self) -> None:
        resources = [_resource("r1")]
        before = copy.deepcopy(resources)

        HealthEngine(_registry(StaticProvider([]))).evaluate(resources)

        self.assertEqual(resources, before)

    def test_resources_iterated_once_by_context(self) -> None:
        resources = CountingResources([_resource("r1")])

        HealthEngine(_registry(StaticProvider([]))).evaluate(resources)

        self.assertEqual(resources.iteration_count, 1)


def _registry(*adapters: Adapter) -> Registry:
    registry = Registry()
    registry.register_many(adapters)
    return registry


def _resource(resource_id: str) -> Resource:
    return Resource(resource_id, "service", resource_id, "active")


def _finding(
    resource_id: str,
    severity: HealthSeverity,
    *,
    code: str = "code",
    message: str = "message",
) -> HealthFinding:
    return HealthFinding("test", code, severity, resource_id, message)


if __name__ == "__main__":
    unittest.main()
