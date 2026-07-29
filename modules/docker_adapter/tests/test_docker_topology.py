from __future__ import annotations

import copy
import json
from typing import Any
import unittest

from zorix_core_model import Resource
from zorix_docker_adapter import DockerAdapter, DockerOutputError
from zorix_mock_adapter import MockAdapter
from zorix_topology_api import TopologyContext, TopologyProvider


CONTAINER_ID_1 = "a" * 64
CONTAINER_ID_2 = "d" * 64
UPPERCASE_CONTAINER_ID = "A" * 64
IMAGE_ID = "sha256:" + "b" * 64
NETWORK_ID_1 = "c" * 64
NETWORK_ID_2 = "e" * 64
CONTAINER_INSPECT = ("container", "inspect")


class FakeDockerCommandRunner:
    def __init__(self, *outputs: str) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: tuple[str, ...]) -> str:
        self.calls.append(tuple(arguments))
        if not self._outputs:
            raise AssertionError("unexpected docker command")

        return self._outputs.pop(0)


class FakeTopologyContext:
    def __init__(self, resources: list[Resource]) -> None:
        self._resources = tuple(resources)
        self._resource_ids = {resource.id for resource in resources}

    def resources(self) -> tuple[Resource, ...]:
        return self._resources

    def has_resource(self, resource_id: str) -> bool:
        return resource_id in self._resource_ids


class DockerTopologyTest(unittest.TestCase):
    def test_docker_adapter_is_topology_provider_but_mock_adapter_is_not(self) -> None:
        self.assertIsInstance(DockerAdapter(FakeDockerCommandRunner()), TopologyProvider)
        self.assertNotIsInstance(MockAdapter(), TopologyProvider)

    def test_empty_context_returns_empty_list_without_inspect(self) -> None:
        runner = FakeDockerCommandRunner()

        relations = DockerAdapter(runner).discover_relations(TopologyContext([]))

        self.assertEqual(relations, [])
        self.assertEqual(runner.calls, [])

    def test_context_without_docker_container_returns_empty_list_without_inspect(self) -> None:
        runner = FakeDockerCommandRunner()
        context = TopologyContext([Resource("container:other", "container", "other", "running")])

        relations = DockerAdapter(runner).discover_relations(context)

        self.assertEqual(relations, [])
        self.assertEqual(runner.calls, [])

    def test_only_docker_container_resources_are_selected_and_deduplicated(self) -> None:
        runner = FakeDockerCommandRunner(_json(_container_payload(CONTAINER_ID_1)))
        context = FakeTopologyContext(
            [
                _container_resource(CONTAINER_ID_1),
                _container_resource(CONTAINER_ID_1),
                Resource("container:other", "container", "other", "running"),
                Resource(f"docker:container:{CONTAINER_ID_1}", "service", "wrong", "running"),
                _image_resource(),
                _network_resource(NETWORK_ID_1),
            ]
        )

        DockerAdapter(runner).discover_relations(context)

        self.assertEqual(runner.calls, [(*CONTAINER_INSPECT, CONTAINER_ID_1)])

    def test_invalid_container_resource_id_option_like_suffix_is_rejected_before_runner(self) -> None:
        runner = FakeDockerCommandRunner()
        context = TopologyContext(
            [
                Resource("docker:container:--help", "container", "bad", "running"),
            ]
        )

        with self.assertRaises(DockerOutputError):
            DockerAdapter(runner).discover_relations(context)

        self.assertEqual(runner.calls, [])

    def test_short_container_resource_id_is_rejected_before_runner(self) -> None:
        runner = FakeDockerCommandRunner()
        context = TopologyContext(
            [
                Resource("docker:container:abc123", "container", "bad", "running"),
            ]
        )

        with self.assertRaises(DockerOutputError):
            DockerAdapter(runner).discover_relations(context)

        self.assertEqual(runner.calls, [])

    def test_non_hex_container_resource_id_is_rejected_before_runner(self) -> None:
        runner = FakeDockerCommandRunner()
        context = TopologyContext(
            [
                Resource(f"docker:container:{'g' * 64}", "container", "bad", "running"),
            ]
        )

        with self.assertRaises(DockerOutputError):
            DockerAdapter(runner).discover_relations(context)

        self.assertEqual(runner.calls, [])

    def test_valid_container_id_is_passed_without_changes(self) -> None:
        runner = FakeDockerCommandRunner(_json(_container_payload(CONTAINER_ID_1)))
        context = TopologyContext(
            [
                _container_resource(CONTAINER_ID_1),
                _image_resource(),
                _network_resource(NETWORK_ID_1),
            ]
        )

        DockerAdapter(runner).discover_relations(context)

        self.assertEqual(runner.calls, [(*CONTAINER_INSPECT, CONTAINER_ID_1)])

    def test_uppercase_hex_container_id_is_allowed(self) -> None:
        runner = FakeDockerCommandRunner(
            _json(_container_payload(UPPERCASE_CONTAINER_ID))
        )
        context = TopologyContext(
            [
                _container_resource(UPPERCASE_CONTAINER_ID),
                _image_resource(),
                _network_resource(NETWORK_ID_1),
            ]
        )

        DockerAdapter(runner).discover_relations(context)

        self.assertEqual(runner.calls, [(*CONTAINER_INSPECT, UPPERCASE_CONTAINER_ID)])

    def test_container_id_order_is_preserved(self) -> None:
        runner = FakeDockerCommandRunner(
            _json(_container_payload(CONTAINER_ID_1), _container_payload(CONTAINER_ID_2))
        )
        context = TopologyContext(
            [
                _container_resource(CONTAINER_ID_2),
                _container_resource(CONTAINER_ID_1),
                _image_resource(),
                _network_resource(NETWORK_ID_1),
            ]
        )

        DockerAdapter(runner).discover_relations(context)

        self.assertEqual(runner.calls, [(*CONTAINER_INSPECT, CONTAINER_ID_2, CONTAINER_ID_1)])

    def test_uses_image_relation_mapping(self) -> None:
        relation = _relations()[0]

        self.assertEqual(relation.type, "uses_image")
        self.assertEqual(relation.source_id, f"docker:container:{CONTAINER_ID_1}")
        self.assertEqual(relation.target_id, f"docker:image:{IMAGE_ID}")
        self.assertEqual(relation.metadata, {"reference": "zorix/api:latest"})

    def test_missing_image_endpoint_skips_uses_image_relation(self) -> None:
        relations = _relations(resources=[_container_resource(CONTAINER_ID_1), _network_resource(NETWORK_ID_1)])

        self.assertEqual([relation.type for relation in relations], ["connected_to"])

    def test_connected_to_relation_mapping(self) -> None:
        relation = _relations()[1]

        self.assertEqual(relation.type, "connected_to")
        self.assertEqual(relation.source_id, f"docker:container:{CONTAINER_ID_1}")
        self.assertEqual(relation.target_id, f"docker:network:{NETWORK_ID_1}")
        self.assertEqual(
            relation.metadata,
            {
                "network_name": "backend",
                "ipv4_address": "172.18.0.2",
                "ipv6_address": "fd00::2",
                "mac_address": "02:42:ac:12:00:02",
            },
        )

    def test_missing_network_id_or_endpoint_skips_connected_relation(self) -> None:
        payload = _container_payload(
            CONTAINER_ID_1,
            networks={
                "missing-id": {},
                "missing-resource": {"NetworkID": NETWORK_ID_2},
                "malformed": "bad",
            },
        )

        relations = _relations(payload=payload)

        self.assertEqual([relation.type for relation in relations], ["uses_image"])

    def test_relation_order_follows_context_and_network_order(self) -> None:
        payload_1 = _container_payload(
            CONTAINER_ID_1,
            networks={
                "backend": {"NetworkID": NETWORK_ID_1},
                "frontend": {"NetworkID": NETWORK_ID_2},
            },
        )
        payload_2 = _container_payload(CONTAINER_ID_2, networks={"backend": {"NetworkID": NETWORK_ID_1}})
        resources = [
            _container_resource(CONTAINER_ID_2),
            _container_resource(CONTAINER_ID_1),
            _image_resource(),
            _network_resource(NETWORK_ID_1),
            _network_resource(NETWORK_ID_2),
        ]

        relations = _relations(payload=_json(payload_1, payload_2), resources=resources)

        self.assertEqual(
            [(relation.source_id, relation.type, relation.target_id) for relation in relations],
            [
                (f"docker:container:{CONTAINER_ID_2}", "uses_image", f"docker:image:{IMAGE_ID}"),
                (f"docker:container:{CONTAINER_ID_2}", "connected_to", f"docker:network:{NETWORK_ID_1}"),
                (f"docker:container:{CONTAINER_ID_1}", "uses_image", f"docker:image:{IMAGE_ID}"),
                (f"docker:container:{CONTAINER_ID_1}", "connected_to", f"docker:network:{NETWORK_ID_1}"),
                (f"docker:container:{CONTAINER_ID_1}", "connected_to", f"docker:network:{NETWORK_ID_2}"),
            ],
        )

    def test_duplicate_relations_are_removed_and_first_metadata_is_preserved(self) -> None:
        payload = _container_payload(
            CONTAINER_ID_1,
            networks={
                "backend": {"NetworkID": NETWORK_ID_1, "IPAddress": "first"},
                "backend-copy": {"NetworkID": NETWORK_ID_1, "IPAddress": "second"},
            },
        )

        relations = _relations(payload=payload)

        self.assertEqual([relation.type for relation in relations], ["uses_image", "connected_to"])
        self.assertEqual(relations[1].metadata["network_name"], "backend")
        self.assertEqual(relations[1].metadata["ipv4_address"], "first")

    def test_context_resources_are_not_mutated(self) -> None:
        resources = [_container_resource(CONTAINER_ID_1), _image_resource(), _network_resource(NETWORK_ID_1)]
        before = copy.deepcopy(resources)

        _relations(resources=resources)

        self.assertEqual(resources, before)

    def test_invalid_json_raises_output_error(self) -> None:
        context = _context()

        with self.assertRaises(DockerOutputError):
            DockerAdapter(FakeDockerCommandRunner("not-json")).discover_relations(context)

    def test_non_object_inspect_item_raises_output_error(self) -> None:
        context = _context()

        with self.assertRaises(DockerOutputError):
            DockerAdapter(FakeDockerCommandRunner(json.dumps([1]))).discover_relations(context)

    def test_repeated_topology_call_does_not_depend_on_discover_cache(self) -> None:
        adapter = DockerAdapter(
            FakeDockerCommandRunner(
                _json(_container_payload(CONTAINER_ID_1)),
                _json(_container_payload(CONTAINER_ID_1, image_reference="zorix/api:2")),
            )
        )
        context = _context()

        first = adapter.discover_relations(context)
        second = adapter.discover_relations(context)

        self.assertEqual(first[0].metadata["reference"], "zorix/api:latest")
        self.assertEqual(second[0].metadata["reference"], "zorix/api:2")


def _relations(
    *,
    payload: dict[str, Any] | str | None = None,
    resources: list[Resource] | None = None,
) -> list[Any]:
    if payload is None:
        output = _json(_container_payload(CONTAINER_ID_1))
    elif isinstance(payload, str):
        output = payload
    else:
        output = _json(payload)

    return DockerAdapter(FakeDockerCommandRunner(output)).discover_relations(
        TopologyContext(resources or [_container_resource(CONTAINER_ID_1), _image_resource(), _network_resource(NETWORK_ID_1)])
    )


def _context() -> TopologyContext:
    return TopologyContext([_container_resource(CONTAINER_ID_1), _image_resource(), _network_resource(NETWORK_ID_1)])


def _container_resource(docker_id: str) -> Resource:
    return Resource(f"docker:container:{docker_id}", "container", docker_id[:12], "running")


def _image_resource() -> Resource:
    return Resource(f"docker:image:{IMAGE_ID}", "image", "zorix/api:latest", "present")


def _network_resource(network_id: str) -> Resource:
    return Resource(f"docker:network:{network_id}", "network", network_id[:12], "present")


def _container_payload(
    docker_id: str,
    *,
    image_id: str = IMAGE_ID,
    image_reference: str = "zorix/api:latest",
    networks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if networks is None:
        networks = {
            "backend": {
                "NetworkID": NETWORK_ID_1,
                "IPAddress": "172.18.0.2",
                "GlobalIPv6Address": "fd00::2",
                "MacAddress": "02:42:ac:12:00:02",
            }
        }

    return {
        "Id": docker_id,
        "Image": image_id,
        "Config": {"Image": image_reference},
        "NetworkSettings": {"Networks": networks},
    }


def _json(*items: dict[str, Any]) -> str:
    return json.dumps(list(items))


if __name__ == "__main__":
    unittest.main()
