from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
import unittest
from unittest.mock import patch

from zorix_core_model import Resource
from zorix_docker_adapter import DockerAdapter, DockerOutputError
from zorix_plugin_loader import PluginLoader
from zorix_presentation import ConsoleRenderer
from zorix_registry import Registry
from zorix_scan_engine import ScanEngine, ScanStatus


ROOT = Path(__file__).resolve().parents[3]
FULL_ID_1 = "a" * 64
FULL_ID_2 = "b" * 64
LIST_ARGUMENTS = ("container", "ls", "--all", "--quiet", "--no-trunc")
DEFAULT_VALUE = object()


class FakeDockerCommandRunner:
    def __init__(self, *outputs: str) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: tuple[str, ...]) -> str:
        self.calls.append(tuple(arguments))
        if not self._outputs:
            raise AssertionError("unexpected docker command")

        return self._outputs.pop(0)


class FalseyDockerCommandRunner(FakeDockerCommandRunner):
    def __bool__(self) -> bool:
        return False


class DockerAdapterTest(unittest.TestCase):
    def test_calls_container_ls_with_exact_arguments(self) -> None:
        runner = FakeDockerCommandRunner("")

        resources = DockerAdapter(runner).discover()

        self.assertEqual(resources, [])
        self.assertEqual(runner.calls, [LIST_ARGUMENTS])

    def test_no_containers_returns_empty_list(self) -> None:
        runner = FakeDockerCommandRunner("\n")

        resources = DockerAdapter(runner).discover()

        self.assertEqual(resources, [])

    def test_no_containers_does_not_call_inspect(self) -> None:
        runner = FakeDockerCommandRunner("")

        DockerAdapter(runner).discover()

        self.assertEqual(len(runner.calls), 1)

    def test_falsey_runner_is_not_replaced_with_default_runner(self) -> None:
        runner = FalseyDockerCommandRunner("")

        with patch("zorix_docker_adapter.adapter.SubprocessDockerCommandRunner") as default_runner:
            resources = DockerAdapter(runner).discover()

        self.assertEqual(resources, [])
        self.assertEqual(runner.calls, [LIST_ARGUMENTS])
        default_runner.assert_not_called()

    def test_empty_lines_from_ls_are_ignored_and_order_is_preserved(self) -> None:
        runner = FakeDockerCommandRunner(
            f"\n {FULL_ID_2} \n\n{FULL_ID_1}\n",
            _inspect_json(_container_payload(docker_id=FULL_ID_2), _container_payload(docker_id=FULL_ID_1)),
        )

        resources = DockerAdapter(runner).discover()

        self.assertEqual(
            runner.calls[1],
            ("container", "inspect", FULL_ID_2, FULL_ID_1),
        )
        self.assertEqual(
            [resource.id for resource in resources],
            [f"docker:container:{FULL_ID_2}", f"docker:container:{FULL_ID_1}"],
        )

    def test_one_container_is_converted_to_resource(self) -> None:
        runner = FakeDockerCommandRunner(
            f"{FULL_ID_1}\n",
            _inspect_json(_container_payload()),
        )

        resources = DockerAdapter(runner).discover()

        self.assertEqual(len(resources), 1)
        self.assertIsInstance(resources[0], Resource)

    def test_multiple_containers_are_converted_to_resources(self) -> None:
        runner = FakeDockerCommandRunner(
            f"{FULL_ID_1}\n{FULL_ID_2}\n",
            _inspect_json(
                _container_payload(docker_id=FULL_ID_1, name="/api"),
                _container_payload(docker_id=FULL_ID_2, name="/worker"),
            ),
        )

        resources = DockerAdapter(runner).discover()

        self.assertEqual([resource.name for resource in resources], ["api", "worker"])

    def test_full_id_and_namespace_are_preserved(self) -> None:
        resource = _single_resource(_container_payload())

        self.assertEqual(resource.id, f"docker:container:{FULL_ID_1}")
        self.assertEqual(resource.metadata["docker_id"], FULL_ID_1)

    def test_resource_type_is_container(self) -> None:
        resource = _single_resource(_container_payload())

        self.assertEqual(resource.type, "container")

    def test_initial_slash_is_removed_from_name(self) -> None:
        resource = _single_resource(_container_payload(name="/zorix-api"))

        self.assertEqual(resource.name, "zorix-api")

    def test_missing_name_uses_first_twelve_id_characters(self) -> None:
        payload = _container_payload()
        payload.pop("Name")

        resource = _single_resource(payload)

        self.assertEqual(resource.name, FULL_ID_1[:12])

    def test_state_status_is_used(self) -> None:
        resource = _single_resource(_container_payload(status="exited"))

        self.assertEqual(resource.state, "exited")

    def test_missing_state_status_uses_unknown(self) -> None:
        payload = _container_payload()
        payload["State"] = {}

        resource = _single_resource(payload)

        self.assertEqual(resource.state, "unknown")

    def test_labels_are_copied(self) -> None:
        resource = _single_resource(
            _container_payload(labels={"com.example.role": "api"})
        )

        self.assertEqual(resource.labels, {"com.example.role": "api"})

    def test_null_labels_produce_empty_dict(self) -> None:
        resource = _single_resource(_container_payload(labels=None))

        self.assertEqual(resource.labels, {})

    def test_non_string_labels_are_skipped(self) -> None:
        payload = [_container_payload(labels={"ok": "yes", "bad": 1, 2: "ignored"})]
        runner = FakeDockerCommandRunner(f"{FULL_ID_1}\n", "ignored")

        with patch("zorix_docker_adapter.adapter.json.loads", return_value=payload):
            resource = DockerAdapter(runner).discover()[0]

        self.assertEqual(resource.labels, {"ok": "yes"})

    def test_metadata_contains_supported_fields(self) -> None:
        resource = _single_resource(_container_payload())

        self.assertEqual(resource.metadata["image"], "nginx:latest")
        self.assertEqual(resource.metadata["image_id"], "sha256:image-id")
        self.assertEqual(resource.metadata["created"], "2026-07-29T10:00:00Z")
        self.assertEqual(resource.metadata["hostname"], "zorix-api-host")
        self.assertEqual(resource.metadata["health"], "healthy")
        self.assertEqual(resource.metadata["restart_policy"], "unless-stopped")

    def test_networks_are_sorted(self) -> None:
        resource = _single_resource(
            _container_payload(networks={"frontend": {}, "backend": {}})
        )

        self.assertEqual(resource.metadata["networks"], "backend,frontend")

    def test_empty_metadata_fields_are_omitted(self) -> None:
        resource = _single_resource(
            _container_payload(
                image="",
                image_id=None,
                created=" ",
                hostname=None,
                health="",
                restart_policy=None,
                networks={},
            )
        )

        self.assertEqual(resource.metadata, {"docker_id": FULL_ID_1})

    def test_invalid_json_raises_output_error(self) -> None:
        runner = FakeDockerCommandRunner(f"{FULL_ID_1}\n", "not-json")

        with self.assertRaises(DockerOutputError):
            DockerAdapter(runner).discover()

    def test_json_object_instead_of_list_raises_output_error(self) -> None:
        runner = FakeDockerCommandRunner(f"{FULL_ID_1}\n", json.dumps({"Id": FULL_ID_1}))

        with self.assertRaises(DockerOutputError):
            DockerAdapter(runner).discover()

    def test_non_object_list_item_raises_output_error(self) -> None:
        runner = FakeDockerCommandRunner(f"{FULL_ID_1}\n", json.dumps([1]))

        with self.assertRaises(DockerOutputError):
            DockerAdapter(runner).discover()

    def test_missing_id_raises_output_error(self) -> None:
        payload = _container_payload()
        payload.pop("Id")
        runner = FakeDockerCommandRunner(f"{FULL_ID_1}\n", _inspect_json(payload))

        with self.assertRaises(DockerOutputError):
            DockerAdapter(runner).discover()

    def test_empty_id_raises_output_error(self) -> None:
        runner = FakeDockerCommandRunner(
            f"{FULL_ID_1}\n",
            _inspect_json(_container_payload(docker_id="   ")),
        )

        with self.assertRaises(DockerOutputError):
            DockerAdapter(runner).discover()

    def test_parsed_payload_is_not_mutated(self) -> None:
        payload = [_container_payload(labels={"ok": "yes"}, networks={"backend": {}})]
        before = copy.deepcopy(payload)
        runner = FakeDockerCommandRunner(f"{FULL_ID_1}\n", "ignored")

        with patch("zorix_docker_adapter.adapter.json.loads", return_value=payload):
            DockerAdapter(runner).discover()

        self.assertEqual(payload, before)

    def test_repeated_discover_with_same_output_returns_equal_resources(self) -> None:
        inspect_output = _inspect_json(_container_payload())
        runner = FakeDockerCommandRunner(
            f"{FULL_ID_1}\n",
            inspect_output,
            f"{FULL_ID_1}\n",
            inspect_output,
        )
        adapter = DockerAdapter(runner)

        first = adapter.discover()
        second = adapter.discover()

        self.assertEqual(first, second)

    def test_minimal_container_payload_is_parsed_defensively(self) -> None:
        resource = _single_resource({"Id": FULL_ID_1})

        self.assertEqual(resource.name, FULL_ID_1[:12])
        self.assertEqual(resource.state, "unknown")
        self.assertEqual(resource.labels, {})
        self.assertEqual(resource.metadata, {"docker_id": FULL_ID_1})


class DockerAdapterIntegrationTest(unittest.TestCase):
    def test_registry_scan_engine_console_renderer_chain(self) -> None:
        runner = FakeDockerCommandRunner(
            f"{FULL_ID_1}\n",
            _inspect_json(_container_payload(name="/zorix-db", networks={"backend": {}})),
        )
        registry = Registry()
        registry.register(DockerAdapter(runner))

        result = ScanEngine(registry).scan()
        output = ConsoleRenderer().render(result, adapter_count=len(registry.adapters()))

        self.assertIs(result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(result.resources), 1)
        self.assertEqual(result.resources[0].metadata["image"], "nginx:latest")
        self.assertEqual(result.errors, ())
        self.assertIn("Adapters: 1\n", output)
        self.assertIn("- Container: zorix-db\n", output)


class DockerPluginLoaderIntegrationTest(unittest.TestCase):
    def test_example_docker_plugin_is_loaded(self) -> None:
        adapters = PluginLoader().load(ROOT / "examples" / "plugins" / "docker")

        self.assertEqual(len(adapters), 1)
        self.assertIsInstance(adapters[0], DockerAdapter)

    def test_example_plugin_does_not_reimplement_adapter(self) -> None:
        plugin_text = (
            ROOT / "examples" / "plugins" / "docker" / "docker_plugin.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("class DockerAdapter", plugin_text)
        self.assertNotIn("def discover", plugin_text)


def _single_resource(payload: dict[str, Any]) -> Resource:
    runner = FakeDockerCommandRunner(f"{FULL_ID_1}\n", _inspect_json(payload))
    resources = DockerAdapter(runner).discover()
    return resources[0]


def _inspect_json(*containers: dict[str, Any]) -> str:
    return json.dumps(list(containers))


def _container_payload(
    *,
    docker_id: object = FULL_ID_1,
    name: object = "/zorix-api",
    status: object = "running",
    labels: object = DEFAULT_VALUE,
    image: object = "nginx:latest",
    image_id: object = "sha256:image-id",
    created: object = "2026-07-29T10:00:00Z",
    hostname: object = "zorix-api-host",
    health: object = "healthy",
    restart_policy: object = "unless-stopped",
    networks: object = DEFAULT_VALUE,
) -> dict[str, Any]:
    if labels is DEFAULT_VALUE:
        labels = {"com.example.service": "api"}

    if networks is DEFAULT_VALUE:
        networks = {"frontend": {}}

    return {
        "Id": docker_id,
        "Name": name,
        "Image": image_id,
        "Created": created,
        "Config": {
            "Image": image,
            "Hostname": hostname,
            "Labels": labels,
        },
        "State": {
            "Status": status,
            "Health": {
                "Status": health,
            },
        },
        "HostConfig": {
            "RestartPolicy": {
                "Name": restart_policy,
            },
        },
        "NetworkSettings": {
            "Networks": networks,
        },
    }


if __name__ == "__main__":
    unittest.main()
