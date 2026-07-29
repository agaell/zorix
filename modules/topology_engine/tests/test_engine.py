from __future__ import annotations

from collections.abc import Iterator
import unittest

from zorix_core_model import Adapter, Resource
from zorix_registry import Registry
from zorix_resource_graph import (
    DuplicateResourceError,
    InvalidRelationError,
    ResourceRelation,
)
from zorix_topology_api import TopologyContext, TopologyProvider
from zorix_topology_engine import (
    InvalidTopologyProviderOutputError,
    TopologyEngine,
    TopologyStatus,
)


class EmptyAdapter(Adapter):
    def __init__(self) -> None:
        self.discover_calls = 0

    def discover(self) -> list[Resource]:
        self.discover_calls += 1
        return []


class EmptyProvider(Adapter):
    def __init__(self) -> None:
        self.received_context: TopologyContext | None = None
        self.discover_calls = 0

    def discover(self) -> list[Resource]:
        self.discover_calls += 1
        return []

    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        return []


class SecondEmptyProvider(EmptyProvider):
    pass


class DependsOnProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        return [ResourceRelation("service:api", "database:main", "depends_on")]


class HostsProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        return [ResourceRelation("server:node-1", "service:api", "hosts")]


class UsesServerProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        return [ResourceRelation("database:main", "server:node-1", "uses_server")]


class MultiRelationProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        return [
            ResourceRelation("service:api", "database:main", "depends_on"),
            ResourceRelation("server:node-1", "service:api", "hosts"),
        ]


class FailingProvider(EmptyProvider):
    def __init__(self, error: Exception | None = None) -> None:
        super().__init__()
        self.error = error or RuntimeError("provider failed")

    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        raise self.error


class EmptyMessageError(Exception):
    def __str__(self) -> str:
        return ""


class EmptyMessageProvider(FailingProvider):
    def __init__(self) -> None:
        super().__init__(EmptyMessageError())


class TupleOutputProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext):
        self.received_context = context
        return ()


class UnknownEndpointProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        return [ResourceRelation("service:api", "cache:missing", "depends_on")]


class DuplicateBatchProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        return [
            ResourceRelation("service:api", "database:main", "depends_on"),
            ResourceRelation("service:api", "database:main", "depends_on", {"reason": "duplicate"}),
        ]


class DuplicateWithExtraProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        self.received_context = context
        return [
            ResourceRelation("service:api", "database:main", "depends_on"),
            ResourceRelation("server:node-1", "service:api", "hosts"),
        ]


class WrongItemProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[object]:
        self.received_context = context
        return [object()]


class KeyboardInterruptProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        raise KeyboardInterrupt()


class SystemExitProvider(EmptyProvider):
    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        raise SystemExit(2)


class DiscoverRaisingProvider(EmptyProvider):
    def discover(self) -> list[Resource]:
        raise AssertionError("TopologyEngine must not call discover")


class SingleUseResources:
    def __init__(self, resources: list[Resource]) -> None:
        self._resources = resources
        self.iterations = 0

    def __iter__(self) -> Iterator[Resource]:
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("resources iterable was consumed more than once")

        return iter(self._resources)


class TopologyEngineTest(unittest.TestCase):
    def test_build_without_providers_returns_success(self) -> None:
        result = _engine_with(EmptyAdapter()).build(_resources())

        self.assertIs(result.status, TopologyStatus.SUCCESS)
        self.assertEqual(result.provider_count, 0)

    def test_build_without_providers_preserves_resources(self) -> None:
        resources = _resources()

        result = _engine_with(EmptyAdapter()).build(resources)

        self.assertEqual(result.graph.resources(), tuple(resources))

    def test_plain_adapter_is_ignored(self) -> None:
        adapter = EmptyAdapter()

        result = _engine_with(adapter).build(_resources())

        self.assertEqual(result.provider_count, 0)
        self.assertEqual(adapter.discover_calls, 0)

    def test_topology_provider_is_detected_with_isinstance(self) -> None:
        provider = EmptyProvider()

        result = _engine_with(provider).build(_resources())

        self.assertIsInstance(provider, TopologyProvider)
        self.assertEqual(result.provider_count, 1)

    def test_provider_count_counts_only_topology_providers(self) -> None:
        result = _engine_with(EmptyAdapter(), EmptyProvider()).build(_resources())

        self.assertEqual(result.provider_count, 1)

    def test_provider_receives_topology_context(self) -> None:
        provider = EmptyProvider()

        _engine_with(provider).build(_resources())

        self.assertIsInstance(provider.received_context, TopologyContext)

    def test_all_providers_receive_one_context(self) -> None:
        first = EmptyProvider()
        second = SecondEmptyProvider()

        _engine_with(first, second).build(_resources())

        self.assertIs(first.received_context, second.received_context)

    def test_context_contains_all_passed_resources(self) -> None:
        provider = EmptyProvider()
        resources = _resources()

        _engine_with(provider).build(resources)

        self.assertEqual(provider.received_context.resources(), tuple(resources))

    def test_resources_generator_is_consumed_once(self) -> None:
        resources = SingleUseResources(_resources())

        _engine_with(EmptyProvider()).build(resources)

        self.assertEqual(resources.iterations, 1)

    def test_provider_returning_empty_list_is_successful(self) -> None:
        result = _engine_with(EmptyProvider()).build(_resources())

        self.assertIs(result.status, TopologyStatus.SUCCESS)
        self.assertEqual(result.successful_provider_count, 1)
        self.assertEqual(result.relation_count, 0)

    def test_one_provider_adds_relation(self) -> None:
        result = _engine_with(DependsOnProvider()).build(_resources())

        self.assertEqual(
            result.graph.relations(),
            (ResourceRelation("service:api", "database:main", "depends_on"),),
        )

    def test_multiple_providers_add_relations(self) -> None:
        result = _engine_with(DependsOnProvider(), HostsProvider()).build(_resources())

        self.assertEqual(len(result.graph.relations()), 2)

    def test_provider_order_is_preserved(self) -> None:
        result = _engine_with(HostsProvider(), DependsOnProvider()).build(_resources())

        self.assertEqual([relation.type for relation in result.graph.relations()], ["hosts", "depends_on"])

    def test_relation_order_inside_provider_is_preserved(self) -> None:
        result = _engine_with(MultiRelationProvider()).build(_resources())

        self.assertEqual([relation.type for relation in result.graph.relations()], ["depends_on", "hosts"])

    def test_global_relation_order_is_preserved(self) -> None:
        result = _engine_with(MultiRelationProvider(), UsesServerProvider()).build(_resources())

        self.assertEqual([relation.type for relation in result.graph.relations()], ["depends_on", "hosts", "uses_server"])

    def test_graph_contains_original_resource_objects(self) -> None:
        resources = _resources()

        result = _engine_with(EmptyProvider()).build(resources)

        self.assertIs(result.graph.resource("service:api"), resources[0])

    def test_outgoing_works_on_built_graph(self) -> None:
        result = _engine_with(DependsOnProvider()).build(_resources())

        self.assertEqual(result.graph.outgoing("service:api")[0].type, "depends_on")

    def test_incoming_works_on_built_graph(self) -> None:
        result = _engine_with(DependsOnProvider()).build(_resources())

        self.assertEqual(result.graph.incoming("database:main")[0].type, "depends_on")

    def test_neighbors_work_on_built_graph(self) -> None:
        result = _engine_with(DependsOnProvider()).build(_resources())

        self.assertEqual(
            [resource.id for resource in result.graph.neighbors("service:api")],
            ["database:main"],
        )

    def test_fail_fast_propagates_original_exception(self) -> None:
        error = RuntimeError("provider failed")
        provider = FailingProvider(error)

        with self.assertRaises(RuntimeError) as context:
            _engine_with(provider).build(_resources())

        self.assertIs(context.exception, error)

    def test_fail_fast_does_not_call_next_provider(self) -> None:
        failing = FailingProvider()
        next_provider = EmptyProvider()

        with self.assertRaises(RuntimeError):
            _engine_with(failing, next_provider).build(_resources())

        self.assertIsNone(next_provider.received_context)

    def test_continue_on_error_records_error(self) -> None:
        result = _engine_with(FailingProvider()).build(_resources(), continue_on_error=True)

        self.assertEqual(len(result.errors), 1)

    def test_continue_on_error_calls_next_provider(self) -> None:
        next_provider = EmptyProvider()

        _engine_with(FailingProvider(), next_provider).build(_resources(), continue_on_error=True)

        self.assertIsNotNone(next_provider.received_context)

    def test_provider_error_contains_full_class_name(self) -> None:
        provider = FailingProvider()

        result = _engine_with(provider).build(_resources(), continue_on_error=True)

        self.assertEqual(result.errors[0].provider, _provider_name(provider))

    def test_provider_error_contains_exception_type(self) -> None:
        result = _engine_with(FailingProvider()).build(_resources(), continue_on_error=True)

        self.assertEqual(result.errors[0].error_type, "RuntimeError")

    def test_provider_error_contains_exception_message(self) -> None:
        result = _engine_with(FailingProvider(RuntimeError("connection failed"))).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertEqual(result.errors[0].message, "connection failed")

    def test_empty_exception_message_is_preserved(self) -> None:
        result = _engine_with(EmptyMessageProvider()).build(_resources(), continue_on_error=True)

        self.assertEqual(result.errors[0].message, "")

    def test_one_error_and_one_success_is_partial(self) -> None:
        result = _engine_with(FailingProvider(), EmptyProvider()).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertIs(result.status, TopologyStatus.PARTIAL)

    def test_all_provider_errors_is_failed(self) -> None:
        result = _engine_with(FailingProvider()).build(_resources(), continue_on_error=True)

        self.assertIs(result.status, TopologyStatus.FAILED)

    def test_all_providers_successful_is_success(self) -> None:
        result = _engine_with(EmptyProvider(), SecondEmptyProvider()).build(_resources())

        self.assertIs(result.status, TopologyStatus.SUCCESS)

    def test_non_list_output_raises_invalid_output_error(self) -> None:
        with self.assertRaises(InvalidTopologyProviderOutputError) as context:
            _engine_with(TupleOutputProvider()).build(_resources())

        self.assertEqual(context.exception.actual_type, "tuple")

    def test_invalid_output_continue_mode_records_provider_error(self) -> None:
        result = _engine_with(TupleOutputProvider()).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertEqual(result.errors[0].error_type, "InvalidTopologyProviderOutputError")

    def test_tuple_output_is_invalid(self) -> None:
        result = _engine_with(TupleOutputProvider()).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertIs(result.status, TopologyStatus.FAILED)

    def test_unknown_endpoint_fail_fast_raises_builder_error(self) -> None:
        with self.assertRaises(InvalidRelationError):
            _engine_with(UnknownEndpointProvider()).build(_resources())

    def test_unknown_endpoint_continue_mode_records_provider_error(self) -> None:
        result = _engine_with(UnknownEndpointProvider()).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertEqual(result.errors[0].error_type, "InvalidRelationError")

    def test_duplicate_relation_from_one_provider_rejects_entire_batch(self) -> None:
        result = _engine_with(DuplicateBatchProvider()).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertIs(result.status, TopologyStatus.FAILED)
        self.assertEqual(result.graph.relations(), ())

    def test_duplicate_relation_between_providers_rejects_second_batch(self) -> None:
        result = _engine_with(DependsOnProvider(), DuplicateWithExtraProvider()).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertIs(result.status, TopologyStatus.PARTIAL)
        self.assertEqual(
            result.graph.relations(),
            (ResourceRelation("service:api", "database:main", "depends_on"),),
        )

    def test_relations_from_first_provider_survive_second_provider_error(self) -> None:
        result = _engine_with(DependsOnProvider(), UnknownEndpointProvider()).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertEqual(
            result.graph.relations(),
            (ResourceRelation("service:api", "database:main", "depends_on"),),
        )

    def test_wrong_list_item_is_provider_error_in_continue_mode(self) -> None:
        result = _engine_with(WrongItemProvider()).build(
            _resources(),
            continue_on_error=True,
        )

        self.assertEqual(result.errors[0].error_type, "TypeError")
        self.assertEqual(result.graph.relations(), ())

    def test_keyboard_interrupt_is_not_caught(self) -> None:
        with self.assertRaises(KeyboardInterrupt):
            _engine_with(KeyboardInterruptProvider()).build(
                _resources(),
                continue_on_error=True,
            )

    def test_system_exit_is_not_caught(self) -> None:
        with self.assertRaises(SystemExit):
            _engine_with(SystemExitProvider()).build(
                _resources(),
                continue_on_error=True,
            )

    def test_topology_context_creation_error_is_not_caught(self) -> None:
        with self.assertRaises(DuplicateResourceError):
            _engine_with(EmptyProvider()).build(
                [_resource("service:api", "service"), _resource("service:api", "service")],
                continue_on_error=True,
            )

    def test_context_error_is_not_provider_error(self) -> None:
        provider = EmptyProvider()

        with self.assertRaises(DuplicateResourceError):
            _engine_with(provider).build(
                [_resource("service:api", "service"), _resource("service:api", "service")],
                continue_on_error=True,
            )

        self.assertIsNone(provider.received_context)

    def test_registry_is_not_modified(self) -> None:
        registry = _registry_with(EmptyProvider())
        before = registry.adapters()

        TopologyEngine(registry).build(_resources())

        self.assertEqual(registry.adapters(), before)

    def test_repeated_build_is_allowed(self) -> None:
        engine = _engine_with(DependsOnProvider())

        first = engine.build(_resources())
        second = engine.build(_resources())

        self.assertEqual(first.relation_count, second.relation_count)

    def test_engine_gets_current_adapter_snapshot_each_build(self) -> None:
        registry = Registry()
        engine = TopologyEngine(registry)
        first = engine.build(_resources())

        registry.register(EmptyProvider())
        second = engine.build(_resources())

        self.assertEqual(first.provider_count, 0)
        self.assertEqual(second.provider_count, 1)

    def test_topology_engine_does_not_call_discover(self) -> None:
        provider = DiscoverRaisingProvider()

        result = _engine_with(provider).build(_resources())

        self.assertIs(result.status, TopologyStatus.SUCCESS)
        self.assertEqual(provider.discover_calls, 0)


def _engine_with(*adapters: Adapter) -> TopologyEngine:
    return TopologyEngine(_registry_with(*adapters))


def _registry_with(*adapters: Adapter) -> Registry:
    registry = Registry()
    registry.register_many(adapters)
    return registry


def _resources() -> list[Resource]:
    return [
        _resource("service:api", "service"),
        _resource("database:main", "database"),
        _resource("server:node-1", "server"),
    ]


def _resource(resource_id: str, resource_type: str) -> Resource:
    return Resource(
        id=resource_id,
        type=resource_type,
        name=resource_id,
        state="active",
    )


def _provider_name(provider: object) -> str:
    provider_type = type(provider)
    return f"{provider_type.__module__}.{provider_type.__qualname__}"


if __name__ == "__main__":
    unittest.main()
