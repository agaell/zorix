from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import unittest

from zorix_core_model import Resource
from zorix_mock_adapter import MockAdapter
from zorix_registry import Registry
from zorix_scan_engine import AdapterScanError, ScanEngine, ScanResult, ScanStatus
from zorix_presentation import ConsoleRenderer


def _resource(resource_id: str, resource_type: str, name: str) -> Resource:
    return Resource(
        id=resource_id,
        type=resource_type,
        name=name,
        state="active",
    )


class ConsoleRendererTest(unittest.TestCase):
    def test_success_with_one_resource(self) -> None:
        result = ScanResult(
            status=ScanStatus.SUCCESS,
            resources=(_resource("service-1", "service", "api"),),
            errors=(),
        )

        text = ConsoleRenderer().render(result, adapter_count=1)

        self.assertEqual(
            text,
            "Status: SUCCESS\n"
            "Adapters: 1\n"
            "Resources: 1\n"
            "\n"
            "Resources:\n"
            "- Service: api\n",
        )

    def test_success_with_multiple_resources(self) -> None:
        result = ScanResult(
            status=ScanStatus.SUCCESS,
            resources=(
                _resource("service-1", "service", "api"),
                _resource("container-1", "container", "nginx"),
            ),
            errors=(),
        )

        text = ConsoleRenderer().render(result, adapter_count=1)

        self.assertEqual(
            text,
            "Status: SUCCESS\n"
            "Adapters: 1\n"
            "Resources: 2\n"
            "\n"
            "Resources:\n"
            "- Service: api\n"
            "- Container: nginx\n",
        )

    def test_success_without_resources(self) -> None:
        result = ScanResult(status=ScanStatus.SUCCESS, resources=(), errors=())

        text = ConsoleRenderer().render(result, adapter_count=0)

        self.assertEqual(text, "Status: SUCCESS\nAdapters: 0\nResources: 0\n")

    def test_outputs_adapter_count_when_provided(self) -> None:
        result = ScanResult(status=ScanStatus.SUCCESS, resources=(), errors=())

        text = ConsoleRenderer().render(result, adapter_count=3)

        self.assertIn("Adapters: 3\n", text)

    def test_omits_adapter_count_when_not_provided(self) -> None:
        result = ScanResult(status=ScanStatus.SUCCESS, resources=(), errors=())

        text = ConsoleRenderer().render(result)

        self.assertNotIn("Adapters:", text)
        self.assertEqual(text, "Status: SUCCESS\nResources: 0\n")

    def test_partial_with_resources_and_errors(self) -> None:
        result = ScanResult(
            status=ScanStatus.PARTIAL,
            resources=(_resource("service-1", "service", "api"),),
            errors=(
                AdapterScanError(
                    adapter="example.adapters.BrokenAdapter",
                    error_type="RuntimeError",
                    message="connection failed",
                ),
            ),
        )

        text = ConsoleRenderer().render(result, adapter_count=2)

        self.assertEqual(
            text,
            "Status: PARTIAL\n"
            "Adapters: 2\n"
            "Resources: 1\n"
            "Errors: 1\n"
            "\n"
            "Resources:\n"
            "- Service: api\n"
            "\n"
            "Errors:\n"
            "- example.adapters.BrokenAdapter: RuntimeError: connection failed\n",
        )

    def test_failed_without_resources(self) -> None:
        result = ScanResult(
            status=ScanStatus.FAILED,
            resources=(),
            errors=(
                AdapterScanError("example.FirstAdapter", "RuntimeError", "first failure"),
                AdapterScanError("example.SecondAdapter", "ValueError", "second failure"),
            ),
        )

        text = ConsoleRenderer().render(result, adapter_count=2)

        self.assertEqual(
            text,
            "Status: FAILED\n"
            "Adapters: 2\n"
            "Resources: 0\n"
            "Errors: 2\n"
            "\n"
            "Errors:\n"
            "- example.FirstAdapter: RuntimeError: first failure\n"
            "- example.SecondAdapter: ValueError: second failure\n",
        )

    def test_multiple_errors_preserve_order(self) -> None:
        result = ScanResult(
            status=ScanStatus.FAILED,
            resources=(),
            errors=(
                AdapterScanError("example.FirstAdapter", "RuntimeError", "first failure"),
                AdapterScanError("example.SecondAdapter", "ValueError", "second failure"),
            ),
        )

        text = ConsoleRenderer().render(result, adapter_count=2)

        self.assertLess(text.index("example.FirstAdapter"), text.index("example.SecondAdapter"))

    def test_formats_error_with_empty_message(self) -> None:
        error = AdapterScanError(adapter="example.Adapter", error_type="RuntimeError", message="")

        text = ConsoleRenderer()._format_error(error)

        self.assertEqual(text, "- example.Adapter: RuntimeError")

    def test_formats_error_with_whitespace_message_as_empty(self) -> None:
        error = AdapterScanError(adapter="example.Adapter", error_type="RuntimeError", message="   ")

        text = ConsoleRenderer()._format_error(error)

        self.assertEqual(text, "- example.Adapter: RuntimeError")

    def test_formats_resource_by_kind_and_name(self) -> None:
        resource = NamedKindResource(kind="service", name="api")

        text = ConsoleRenderer()._format_resource(resource)

        self.assertEqual(text, "- Service: api")

    def test_formats_resource_by_type_and_name(self) -> None:
        resource = TypedResource(type="container", name="nginx")

        text = ConsoleRenderer()._format_resource(resource)

        self.assertEqual(text, "- Container: nginx")

    def test_resource_falls_back_to_class_name(self) -> None:
        resource = UnknownResource()

        text = ConsoleRenderer()._format_resource(resource)

        self.assertEqual(text, "- UnknownResource: UnknownResource")

    def test_resource_falls_back_to_id(self) -> None:
        resource = IdOnlyResource(id="resource-1")

        text = ConsoleRenderer()._format_resource(resource)

        self.assertEqual(text, "- IdOnlyResource: resource-1")

    def test_resource_falls_back_to_identifier(self) -> None:
        resource = IdentifierOnlyResource(identifier="resource-1")

        text = ConsoleRenderer()._format_resource(resource)

        self.assertEqual(text, "- IdentifierOnlyResource: resource-1")

    def test_dataclass_without_name_id_or_identifier(self) -> None:
        resource = Network(cidr="10.0.0.0/24", scope="private", _secret="hidden")

        text = ConsoleRenderer()._format_resource(resource)

        self.assertEqual(text, "- Network: cidr=10.0.0.0/24, scope=private")

    def test_empty_dataclass_uses_class_name(self) -> None:
        resource = EmptyDataclass()

        text = ConsoleRenderer()._format_resource(resource)

        self.assertEqual(text, "- EmptyDataclass: EmptyDataclass")

    def test_unknown_object_does_not_break_renderer(self) -> None:
        result = ScanResult(status=ScanStatus.SUCCESS, resources=(UnknownResource(),), errors=())

        text = ConsoleRenderer().render(result)

        self.assertIn("- UnknownResource: UnknownResource\n", text)

    def test_empty_string_representation_uses_class_name(self) -> None:
        resource = EmptyStringResource()

        text = ConsoleRenderer()._format_resource(resource)

        self.assertEqual(text, "- EmptyStringResource: EmptyStringResource")

    def test_result_ends_with_exactly_one_newline(self) -> None:
        result = ScanResult(status=ScanStatus.SUCCESS, resources=(), errors=())

        text = ConsoleRenderer().render(result)

        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_no_extra_blank_lines(self) -> None:
        result = ScanResult(
            status=ScanStatus.SUCCESS,
            resources=(_resource("service-1", "service", "api"),),
            errors=(),
        )

        text = ConsoleRenderer().render(result)

        self.assertNotIn("\n\n\n", text)

    def test_renderer_does_not_change_scan_result(self) -> None:
        result = ScanResult(
            status=ScanStatus.PARTIAL,
            resources=(_resource("service-1", "service", "api"),),
            errors=(AdapterScanError("example.Adapter", "RuntimeError", "failed"),),
        )
        original = (result.status, result.resources, result.errors)

        ConsoleRenderer().render(result)

        self.assertEqual((result.status, result.resources, result.errors), original)

    def test_renderer_does_not_change_resource(self) -> None:
        resource = _resource("service-1", "service", "api")
        original = (
            resource.id,
            resource.type,
            resource.name,
            resource.state,
            dict(resource.metadata),
            dict(resource.labels),
        )
        result = ScanResult(status=ScanStatus.SUCCESS, resources=(resource,), errors=())

        ConsoleRenderer().render(result)

        self.assertEqual(
            (
                resource.id,
                resource.type,
                resource.name,
                resource.state,
                dict(resource.metadata),
                dict(resource.labels),
            ),
            original,
        )

    def test_render_is_repeatable(self) -> None:
        result = ScanResult(
            status=ScanStatus.SUCCESS,
            resources=(_resource("service-1", "service", "api"),),
            errors=(),
        )
        renderer = ConsoleRenderer()

        first_text = renderer.render(result)
        second_text = renderer.render(result)

        self.assertEqual(first_text, second_text)


class PresentationIntegrationTest(unittest.TestCase):
    def test_mock_adapter_registry_scan_engine_console_renderer_chain(self) -> None:
        registry = Registry()
        registry.register(MockAdapter())

        result = ScanEngine(registry).scan()
        text = ConsoleRenderer().render(result, adapter_count=len(registry.adapters()))
        resource_types = Counter(resource.type for resource in result.resources)

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(result.resources), 5)
        self.assertEqual(resource_types["service"], 2)
        self.assertIn("- Service: mock-api\n", text)
        self.assertIn("- Container: mock-runtime\n", text)
        self.assertIn("- User: mock-admin\n", text)


@dataclass(frozen=True)
class NamedKindResource:
    kind: str
    name: str


@dataclass(frozen=True)
class TypedResource:
    type: str
    name: str


class UnknownResource:
    pass


class IdOnlyResource:
    def __init__(self, id: str) -> None:
        self.id = id


class IdentifierOnlyResource:
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier


@dataclass(frozen=True)
class Network:
    cidr: str
    scope: str
    _secret: str


@dataclass(frozen=True)
class EmptyDataclass:
    pass


class EmptyStringResource:
    def __str__(self) -> str:
        return ""


if __name__ == "__main__":
    unittest.main()
