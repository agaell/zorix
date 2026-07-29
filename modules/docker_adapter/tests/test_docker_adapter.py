from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import unittest
from unittest.mock import patch

from zorix_core_model import Adapter
from zorix_docker_adapter import DockerAdapter
from zorix_plugin_loader import PluginLoader
from zorix_presentation import ConsoleRenderer
from zorix_registry import Registry
from zorix_scan_engine import ScanEngine, ScanStatus
from zorix_topology_api import TopologyProvider


ROOT = Path(__file__).resolve().parents[3]
CONTAINER_ID = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
NETWORK_ID = "c" * 64
CONTAINER_LIST = ("container", "ls", "--all", "--quiet", "--no-trunc")
CONTAINER_INSPECT = ("container", "inspect")
IMAGE_LIST = ("image", "ls", "--all", "--quiet", "--no-trunc")
IMAGE_INSPECT = ("image", "inspect")
NETWORK_LIST = ("network", "ls", "--quiet", "--no-trunc")
NETWORK_INSPECT = ("network", "inspect")


class ExpectedDockerCommandRunner:
    def __init__(self, *steps: tuple[tuple[str, ...], str | BaseException]) -> None:
        self._steps = list(steps)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: tuple[str, ...]) -> str:
        self.calls.append(tuple(arguments))
        if not self._steps:
            raise AssertionError(f"unexpected docker command: {arguments!r}")

        expected_arguments, output = self._steps.pop(0)
        if tuple(arguments) != expected_arguments:
            raise AssertionError(
                f"expected {expected_arguments!r}, got {tuple(arguments)!r}"
            )

        if isinstance(output, BaseException):
            raise output

        return output


class FalseyDockerCommandRunner(ExpectedDockerCommandRunner):
    def __bool__(self) -> bool:
        return False


class DockerAdapterTest(unittest.TestCase):
    def test_adapter_is_core_adapter_and_topology_provider(self) -> None:
        adapter = DockerAdapter(_empty_runner())

        self.assertIsInstance(adapter, Adapter)
        self.assertIsInstance(adapter, TopologyProvider)

    def test_falsey_runner_is_not_replaced_with_default_runner(self) -> None:
        runner = FalseyDockerCommandRunner(
            (CONTAINER_LIST, ""),
            (IMAGE_LIST, ""),
            (NETWORK_LIST, ""),
        )

        with patch("zorix_docker_adapter.adapter.SubprocessDockerCommandRunner") as default_runner:
            resources = DockerAdapter(runner).discover()

        self.assertEqual(resources, [])
        self.assertEqual(runner.calls, [CONTAINER_LIST, IMAGE_LIST, NETWORK_LIST])
        default_runner.assert_not_called()

    def test_no_ids_skip_all_inspect_commands(self) -> None:
        runner = _empty_runner()

        resources = DockerAdapter(runner).discover()

        self.assertEqual(resources, [])
        self.assertEqual(runner.calls, [CONTAINER_LIST, IMAGE_LIST, NETWORK_LIST])

    def test_discover_calls_inventory_commands_in_order(self) -> None:
        runner = ExpectedDockerCommandRunner(
            (CONTAINER_LIST, f"{CONTAINER_ID}\n"),
            ((*CONTAINER_INSPECT, CONTAINER_ID), _json(_container_payload())),
            (IMAGE_LIST, f"{IMAGE_ID}\n"),
            ((*IMAGE_INSPECT, IMAGE_ID), _json(_image_payload())),
            (NETWORK_LIST, f"{NETWORK_ID}\n"),
            ((*NETWORK_INSPECT, NETWORK_ID), _json(_network_payload())),
        )

        DockerAdapter(runner).discover()

        self.assertEqual(
            runner.calls,
            [
                CONTAINER_LIST,
                (*CONTAINER_INSPECT, CONTAINER_ID),
                IMAGE_LIST,
                (*IMAGE_INSPECT, IMAGE_ID),
                NETWORK_LIST,
                (*NETWORK_INSPECT, NETWORK_ID),
            ],
        )

    def test_image_ids_are_deduplicated_before_inspect(self) -> None:
        runner = ExpectedDockerCommandRunner(
            (CONTAINER_LIST, ""),
            (IMAGE_LIST, f"\n {IMAGE_ID} \n{IMAGE_ID}\nsha256:other\n"),
            ((*IMAGE_INSPECT, IMAGE_ID, "sha256:other"), _json(_image_payload())),
            (NETWORK_LIST, ""),
        )

        DockerAdapter(runner).discover()

        self.assertIn((*IMAGE_INSPECT, IMAGE_ID, "sha256:other"), runner.calls)

    def test_network_ids_are_deduplicated_before_inspect(self) -> None:
        runner = ExpectedDockerCommandRunner(
            (CONTAINER_LIST, ""),
            (IMAGE_LIST, ""),
            (NETWORK_LIST, f"{NETWORK_ID}\n{NETWORK_ID}\nother-network\n"),
            ((*NETWORK_INSPECT, NETWORK_ID, "other-network"), _json(_network_payload())),
        )

        DockerAdapter(runner).discover()

        self.assertIn((*NETWORK_INSPECT, NETWORK_ID, "other-network"), runner.calls)

    def test_discover_returns_resources_in_category_order(self) -> None:
        runner = _full_inventory_runner()

        resources = DockerAdapter(runner).discover()

        self.assertEqual(
            [resource.type for resource in resources],
            ["container", "image", "network"],
        )
        self.assertEqual([resource.name for resource in resources], ["zorix-api", "zorix/api:latest", "backend"])

    def test_container_resource_semantics_are_preserved(self) -> None:
        resource = _single_container_resource(_container_payload())

        self.assertEqual(resource.id, f"docker:container:{CONTAINER_ID}")
        self.assertEqual(resource.type, "container")
        self.assertEqual(resource.name, "zorix-api")
        self.assertEqual(resource.state, "running")
        self.assertEqual(resource.labels, {"com.example.service": "api"})
        self.assertEqual(resource.metadata["docker_id"], CONTAINER_ID)
        self.assertEqual(resource.metadata["image"], "zorix/api:latest")
        self.assertEqual(resource.metadata["image_id"], IMAGE_ID)
        self.assertEqual(resource.metadata["networks"], "backend")

    def test_missing_container_values_use_fallbacks(self) -> None:
        resource = _single_container_resource({"Id": CONTAINER_ID})

        self.assertEqual(resource.name, CONTAINER_ID[:12])
        self.assertEqual(resource.state, "unknown")
        self.assertEqual(resource.labels, {})
        self.assertEqual(resource.metadata, {"docker_id": CONTAINER_ID})

    def test_discover_returns_all_three_resource_types(self) -> None:
        resources = DockerAdapter(_full_inventory_runner()).discover()

        self.assertEqual(len(resources), 3)
        self.assertEqual({resource.type for resource in resources}, {"container", "image", "network"})

    def test_repeated_discover_with_same_output_returns_equal_resources(self) -> None:
        runner = ExpectedDockerCommandRunner(
            *_full_inventory_steps(),
            *_full_inventory_steps(),
        )
        adapter = DockerAdapter(runner)

        first = adapter.discover()
        second = adapter.discover()

        self.assertEqual(first, second)

    def test_docker_command_error_is_propagated(self) -> None:
        error = RuntimeError("docker failed")
        runner = ExpectedDockerCommandRunner((CONTAINER_LIST, error))

        with self.assertRaises(RuntimeError) as context:
            DockerAdapter(runner).discover()

        self.assertIs(context.exception, error)


class DockerAdapterIntegrationTest(unittest.TestCase):
    def test_registry_scan_engine_console_renderer_chain(self) -> None:
        registry = Registry()
        registry.register(DockerAdapter(_full_inventory_runner()))

        result = ScanEngine(registry).scan()
        output = ConsoleRenderer().render(result, adapter_count=len(registry.adapters()))

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(result.resources), 3)
        self.assertEqual(result.errors, ())
        self.assertIn("Adapters: 1\n", output)
        self.assertIn("Resources: 3\n", output)
        self.assertIn("- Container: zorix-api\n", output)
        self.assertIn("- Image: zorix/api:latest\n", output)
        self.assertIn("- Network: backend\n", output)


class DockerPluginLoaderIntegrationTest(unittest.TestCase):
    def test_example_docker_plugin_is_loaded_with_topology_capability(self) -> None:
        adapters = PluginLoader().load(ROOT / "examples" / "plugins" / "docker")

        self.assertEqual(len(adapters), 1)
        self.assertIsInstance(adapters[0], DockerAdapter)
        self.assertIsInstance(adapters[0], TopologyProvider)

    def test_example_plugin_does_not_reimplement_adapter(self) -> None:
        plugin_text = (
            ROOT / "examples" / "plugins" / "docker" / "docker_plugin.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("class DockerAdapter", plugin_text)
        self.assertNotIn("def discover", plugin_text)
        self.assertIn("Adapter = DockerAdapter", plugin_text)


def _empty_runner() -> ExpectedDockerCommandRunner:
    return ExpectedDockerCommandRunner(
        (CONTAINER_LIST, ""),
        (IMAGE_LIST, ""),
        (NETWORK_LIST, ""),
    )


def _full_inventory_runner() -> ExpectedDockerCommandRunner:
    return ExpectedDockerCommandRunner(*_full_inventory_steps())


def _full_inventory_steps() -> tuple[tuple[tuple[str, ...], str], ...]:
    return (
        (CONTAINER_LIST, f"{CONTAINER_ID}\n"),
        ((*CONTAINER_INSPECT, CONTAINER_ID), _json(_container_payload())),
        (IMAGE_LIST, f"{IMAGE_ID}\n"),
        ((*IMAGE_INSPECT, IMAGE_ID), _json(_image_payload())),
        (NETWORK_LIST, f"{NETWORK_ID}\n"),
        ((*NETWORK_INSPECT, NETWORK_ID), _json(_network_payload())),
    )


def _single_container_resource(payload: dict[str, Any]) -> Any:
    runner = ExpectedDockerCommandRunner(
        (CONTAINER_LIST, f"{CONTAINER_ID}\n"),
        ((*CONTAINER_INSPECT, CONTAINER_ID), _json(payload)),
        (IMAGE_LIST, ""),
        (NETWORK_LIST, ""),
    )
    return DockerAdapter(runner).discover()[0]


def _json(*items: dict[str, Any]) -> str:
    return json.dumps(list(items))


def _container_payload(
    *,
    docker_id: object = CONTAINER_ID,
    name: object = "/zorix-api",
    status: object = "running",
    labels: object = None,
    image_reference: object = "zorix/api:latest",
    image_id: object = IMAGE_ID,
    networks: object = None,
) -> dict[str, Any]:
    if labels is None:
        labels = {"com.example.service": "api"}

    if networks is None:
        networks = {
            "backend": {
                "NetworkID": NETWORK_ID,
                "IPAddress": "172.18.0.2",
                "GlobalIPv6Address": "",
                "MacAddress": "02:42:ac:12:00:02",
            }
        }

    return {
        "Id": docker_id,
        "Name": name,
        "Image": image_id,
        "Created": "2026-07-29T10:00:00Z",
        "Config": {
            "Image": image_reference,
            "Hostname": "zorix-api-host",
            "Labels": labels,
        },
        "State": {
            "Status": status,
            "Health": {"Status": "healthy"},
        },
        "HostConfig": {
            "RestartPolicy": {"Name": "unless-stopped"},
        },
        "NetworkSettings": {"Networks": networks},
    }


def _image_payload() -> dict[str, Any]:
    return {
        "Id": IMAGE_ID,
        "RepoTags": ["zorix/api:latest"],
        "RepoDigests": ["zorix/api@sha256:digest"],
        "Created": "2026-07-29T09:00:00Z",
        "Architecture": "arm64",
        "Os": "linux",
        "Size": 42,
        "Config": {"Labels": {"org.opencontainers.image.title": "zorix-api"}},
    }


def _network_payload() -> dict[str, Any]:
    return {
        "Id": NETWORK_ID,
        "Name": "backend",
        "Driver": "bridge",
        "Scope": "local",
        "Created": "2026-07-29T08:00:00Z",
        "Internal": False,
        "Attachable": False,
        "Ingress": False,
        "EnableIPv6": False,
        "Labels": {"com.example.network": "backend"},
        "IPAM": {
            "Driver": "default",
            "Config": [{"Subnet": "172.18.0.0/16", "Gateway": "172.18.0.1"}],
        },
    }


if __name__ == "__main__":
    unittest.main()
