from __future__ import annotations

import builtins
import copy
import json
from typing import Any
import unittest
from unittest.mock import patch

from zorix_core_model import Resource
from zorix_docker_adapter import DockerAdapter
from zorix_presentation import TopologyConsoleRenderer
from zorix_registry import Registry
from zorix_resource_graph import ResourceGraph, ResourceGraphBuilder, ResourceRelation
from zorix_scan_engine import ScanEngine
from zorix_topology_engine import (
    TopologyEngine,
    TopologyProviderError,
    TopologyResult,
    TopologyStatus,
)


CONTAINER_ID = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
NETWORK_ID = "c" * 64


class SpyResourceGraph(ResourceGraph):
    def __init__(
        self,
        resources: tuple[Resource, ...],
        relations: tuple[ResourceRelation, ...],
    ) -> None:
        super().__init__(resources, relations)
        self.lookups: list[str] = []

    def resource(self, resource_id: str) -> Resource:
        self.lookups.append(resource_id)
        return super().resource(resource_id)


class FakeDockerCommandRunner:
    def __init__(self, *outputs: str) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: tuple[str, ...]) -> str:
        self.calls.append(tuple(arguments))
        if not self._outputs:
            raise AssertionError("unexpected docker command")

        return self._outputs.pop(0)


class TopologyConsoleRendererTest(unittest.TestCase):
    def test_success_with_relations(self) -> None:
        result = _success_result()

        text = TopologyConsoleRenderer().render(result)

        self.assertEqual(
            text,
            "Topology: SUCCESS\n"
            "Providers: 1\n"
            "Successful providers: 1\n"
            "Failed providers: 0\n"
            "Resources: 3\n"
            "Relations: 2\n"
            "\n"
            "Relations:\n"
            "- Container zorix-api --uses_image--> Image zorix/api:latest\n"
            "- Container zorix-api --connected_to--> Network backend\n",
        )

    def test_success_without_relations(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.SUCCESS,
            graph=_graph((_resource("service:api", "service", "api"),), ()),
            errors=(),
            provider_count=1,
            successful_provider_count=1,
        )

        text = TopologyConsoleRenderer().render(result)

        self.assertEqual(
            text,
            "Topology: SUCCESS\n"
            "Providers: 1\n"
            "Successful providers: 1\n"
            "Failed providers: 0\n"
            "Resources: 1\n"
            "Relations: 0\n",
        )

    def test_success_without_providers(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.SUCCESS,
            graph=_graph(
                (
                    _resource("service:api", "service", "api"),
                    _resource("database:main", "database", "main"),
                    _resource("queue:jobs", "queue", "jobs"),
                ),
                (),
            ),
            errors=(),
            provider_count=0,
            successful_provider_count=0,
        )

        text = TopologyConsoleRenderer().render(result)

        self.assertEqual(
            text,
            "Topology: SUCCESS\n"
            "Providers: 0\n"
            "Successful providers: 0\n"
            "Failed providers: 0\n"
            "Resources: 3\n"
            "Relations: 0\n",
        )

    def test_partial_with_relations_and_error(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.PARTIAL,
            graph=_success_graph(),
            errors=(TopologyProviderError("example.BrokenProvider", "RuntimeError", "connection failed"),),
            provider_count=2,
            successful_provider_count=1,
        )

        text = TopologyConsoleRenderer().render(result)

        self.assertEqual(
            text,
            "Topology: PARTIAL\n"
            "Providers: 2\n"
            "Successful providers: 1\n"
            "Failed providers: 1\n"
            "Resources: 3\n"
            "Relations: 2\n"
            "Errors: 1\n"
            "\n"
            "Relations:\n"
            "- Container zorix-api --uses_image--> Image zorix/api:latest\n"
            "- Container zorix-api --connected_to--> Network backend\n"
            "\n"
            "Errors:\n"
            "- example.BrokenProvider: RuntimeError: connection failed\n",
        )

    def test_failed_with_error(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.FAILED,
            graph=_graph((_resource("service:api", "service", "api"),), ()),
            errors=(TopologyProviderError("example.BrokenProvider", "RuntimeError", "connection failed"),),
            provider_count=1,
            successful_provider_count=0,
        )

        text = TopologyConsoleRenderer().render(result)

        self.assertEqual(
            text,
            "Topology: FAILED\n"
            "Providers: 1\n"
            "Successful providers: 0\n"
            "Failed providers: 1\n"
            "Resources: 1\n"
            "Relations: 0\n"
            "Errors: 1\n"
            "\n"
            "Errors:\n"
            "- example.BrokenProvider: RuntimeError: connection failed\n",
        )

    def test_summary_counts_resources_and_relations(self) -> None:
        text = TopologyConsoleRenderer().render(_success_result())

        self.assertIn("Resources: 3\n", text)
        self.assertIn("Relations: 2\n", text)

    def test_relations_preserve_graph_order(self) -> None:
        text = TopologyConsoleRenderer().render(_success_result())

        self.assertLess(text.index("uses_image"), text.index("connected_to"))

    def test_errors_preserve_result_order(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.FAILED,
            graph=_graph((_resource("service:api", "service", "api"),), ()),
            errors=(
                TopologyProviderError("example.First", "RuntimeError", "first"),
                TopologyProviderError("example.Second", "ValueError", "second"),
            ),
            provider_count=2,
            successful_provider_count=0,
        )

        text = TopologyConsoleRenderer().render(result)

        self.assertLess(text.index("example.First"), text.index("example.Second"))

    def test_source_and_target_resources_are_loaded_through_graph(self) -> None:
        resources = (
            _resource("service:api", "service", "api"),
            _resource("database:main", "database", "main"),
        )
        relation = ResourceRelation("service:api", "database:main", "depends_on")
        graph = SpyResourceGraph(resources, (relation,))

        TopologyConsoleRenderer()._format_relation(relation, graph)

        self.assertEqual(graph.lookups, ["service:api", "database:main"])

    def test_relation_type_is_not_transformed(self) -> None:
        text = TopologyConsoleRenderer().render(_success_result())

        self.assertIn("--uses_image-->", text)

    def test_resource_type_display_rules(self) -> None:
        renderer = TopologyConsoleRenderer()

        self.assertEqual(renderer._format_relation(
            ResourceRelation("container:1", "docker_network:1", "connected_to"),
            _graph(
                (
                    _resource("container:1", "container", "api"),
                    _resource("docker_network:1", "docker_network", "backend"),
                ),
                (ResourceRelation("container:1", "docker_network:1", "connected_to"),),
            ),
        ), "- Container api --connected_to--> DockerNetwork backend")

        self.assertEqual(renderer._format_relation(
            ResourceRelation("load-balancer:1", "service:api", "routes_to"),
            _graph(
                (
                    _resource("load-balancer:1", "load-balancer", "edge"),
                    _resource("service:api", "service", "api"),
                ),
                (ResourceRelation("load-balancer:1", "service:api", "routes_to"),),
            ),
        ), "- LoadBalancer edge --routes_to--> Service api")

    def test_resource_type_falls_back_to_class_name(self) -> None:
        resource = Resource("resource:1", " ", "named", "active")

        text = TopologyConsoleRenderer()._format_relation(
            ResourceRelation("resource:1", "service:api", "uses"),
            _graph(
                (resource, _resource("service:api", "service", "api")),
                (ResourceRelation("resource:1", "service:api", "uses"),),
            ),
        )

        self.assertEqual(text, "- Resource named --uses--> Service api")

    def test_resource_name_fallbacks(self) -> None:
        resource = Resource("resource:1", "service", " ", "active")
        resource.name = 12  # type: ignore[assignment]

        text = TopologyConsoleRenderer()._format_relation(
            ResourceRelation("resource:1", "database:main", "depends_on"),
            _graph(
                (resource, _resource("database:main", "database", "main")),
                (ResourceRelation("resource:1", "database:main", "depends_on"),),
            ),
        )

        self.assertEqual(text, "- Service resource:1 --depends_on--> Database main")

    def test_relation_metadata_is_not_rendered(self) -> None:
        result = TopologyResult(
            status=TopologyStatus.SUCCESS,
            graph=_graph(
                (
                    _resource("container:api", "container", "api"),
                    _resource("image:api", "image", "image"),
                ),
                (
                    ResourceRelation(
                        "container:api",
                        "image:api",
                        "uses_image",
                        {"reference": "secret-reference"},
                    ),
                ),
            ),
            errors=(),
            provider_count=1,
            successful_provider_count=1,
        )

        text = TopologyConsoleRenderer().render(result)

        self.assertNotIn("secret-reference", text)
        self.assertNotIn("reference", text)

    def test_error_empty_and_whitespace_messages(self) -> None:
        renderer = TopologyConsoleRenderer()

        self.assertEqual(
            renderer._format_error(TopologyProviderError("example.Empty", "RuntimeError", "")),
            "- example.Empty: RuntimeError",
        )
        self.assertEqual(
            renderer._format_error(TopologyProviderError("example.Space", "RuntimeError", "   ")),
            "- example.Space: RuntimeError",
        )

    def test_renderer_does_not_use_print(self) -> None:
        result = _success_result()

        with patch.object(builtins, "print", side_effect=AssertionError("print called")):
            text = TopologyConsoleRenderer().render(result)

        self.assertIsInstance(text, str)

    def test_newline_contract_and_blank_lines(self) -> None:
        text = TopologyConsoleRenderer().render(_success_result())

        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        self.assertNotIn("\n\n\n", text)

    def test_repeated_render_is_identical(self) -> None:
        renderer = TopologyConsoleRenderer()
        result = _success_result()

        self.assertEqual(renderer.render(result), renderer.render(result))

    def test_render_does_not_mutate_result_graph_resources_or_relations(self) -> None:
        result = _success_result()
        original_result = (
            result.status,
            result.graph,
            result.errors,
            result.provider_count,
            result.successful_provider_count,
        )
        original_resources = copy.deepcopy(result.graph.resources())
        original_relations = result.graph.relations()

        TopologyConsoleRenderer().render(result)

        self.assertEqual(
            (
                result.status,
                result.graph,
                result.errors,
                result.provider_count,
                result.successful_provider_count,
            ),
            original_result,
        )
        self.assertEqual(result.graph.resources(), original_resources)
        self.assertEqual(result.graph.relations(), original_relations)


class DockerTopologyRendererIntegrationTest(unittest.TestCase):
    def test_docker_topology_chain_renders_plain_text(self) -> None:
        registry = Registry()
        registry.register(
            DockerAdapter(
                FakeDockerCommandRunner(
                    f"{CONTAINER_ID}\n",
                    _json(_container_payload()),
                    f"{IMAGE_ID}\n",
                    _json(_image_payload()),
                    f"{NETWORK_ID}\n",
                    _json(_network_payload()),
                    _json(_container_payload()),
                )
            )
        )

        scan_result = ScanEngine(registry).scan()
        topology_result = TopologyEngine(registry).build(scan_result.resources)
        text = TopologyConsoleRenderer().render(topology_result)

        self.assertEqual(
            text,
            "Topology: SUCCESS\n"
            "Providers: 1\n"
            "Successful providers: 1\n"
            "Failed providers: 0\n"
            "Resources: 3\n"
            "Relations: 2\n"
            "\n"
            "Relations:\n"
            "- Container zorix-api --uses_image--> Image zorix/api:latest\n"
            "- Container zorix-api --connected_to--> Network backend\n",
        )


def _success_result() -> TopologyResult:
    return TopologyResult(
        status=TopologyStatus.SUCCESS,
        graph=_success_graph(),
        errors=(),
        provider_count=1,
        successful_provider_count=1,
    )


def _success_graph() -> ResourceGraph:
    return _graph(
        (
            _resource("docker:container:api", "container", "zorix-api"),
            _resource("docker:image:api", "image", "zorix/api:latest"),
            _resource("docker:network:backend", "network", "backend"),
        ),
        (
            ResourceRelation("docker:container:api", "docker:image:api", "uses_image"),
            ResourceRelation("docker:container:api", "docker:network:backend", "connected_to"),
        ),
    )


def _graph(
    resources: tuple[Resource, ...],
    relations: tuple[ResourceRelation, ...],
) -> ResourceGraph:
    builder = ResourceGraphBuilder()
    builder.add_resources(resources)
    builder.add_relations(relations)
    return builder.build()


def _resource(resource_id: str, resource_type: Any, name: Any) -> Resource:
    return Resource(resource_id, resource_type, name, "active")


def _json(*items: dict[str, Any]) -> str:
    return json.dumps(list(items))


def _container_payload() -> dict[str, Any]:
    return {
        "Id": CONTAINER_ID,
        "Name": "/zorix-api",
        "Image": IMAGE_ID,
        "Config": {"Image": "zorix/api:latest", "Labels": {}},
        "State": {"Status": "running"},
        "NetworkSettings": {
            "Networks": {
                "backend": {
                    "NetworkID": NETWORK_ID,
                    "IPAddress": "172.18.0.2",
                }
            }
        },
    }


def _image_payload() -> dict[str, Any]:
    return {"Id": IMAGE_ID, "RepoTags": ["zorix/api:latest"], "Config": {"Labels": {}}}


def _network_payload() -> dict[str, Any]:
    return {"Id": NETWORK_ID, "Name": "backend", "Labels": {}}


if __name__ == "__main__":
    unittest.main()
