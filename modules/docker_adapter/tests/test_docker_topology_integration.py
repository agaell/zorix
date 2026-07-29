from __future__ import annotations

import json
from typing import Any
import unittest

from zorix_docker_adapter import DockerAdapter
from zorix_registry import Registry
from zorix_scan_engine import ScanEngine, ScanStatus
from zorix_topology_api import TopologyProvider
from zorix_topology_engine import TopologyEngine, TopologyStatus


CONTAINER_ID = "a" * 64
IMAGE_ID = "sha256:" + "b" * 64
NETWORK_ID = "c" * 64


class FakeDockerCommandRunner:
    def __init__(self, *outputs: str) -> None:
        self._outputs = list(outputs)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: tuple[str, ...]) -> str:
        self.calls.append(tuple(arguments))
        if not self._outputs:
            raise AssertionError("unexpected docker command")

        return self._outputs.pop(0)


class DockerTopologyIntegrationTest(unittest.TestCase):
    def test_scan_resources_can_build_docker_topology_graph(self) -> None:
        adapter = DockerAdapter(
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
        registry = Registry()
        registry.register(adapter)

        scan_result = ScanEngine(registry).scan()
        topology_result = TopologyEngine(registry).build(scan_result.resources)
        graph = topology_result.graph
        relations = graph.relations()
        container_id = f"docker:container:{CONTAINER_ID}"
        image_id = f"docker:image:{IMAGE_ID}"
        network_id = f"docker:network:{NETWORK_ID}"

        self.assertIs(scan_result.status, ScanStatus.SUCCESS)
        self.assertEqual(len(scan_result.resources), 3)
        self.assertIsInstance(adapter, TopologyProvider)
        self.assertIs(topology_result.status, TopologyStatus.SUCCESS)
        self.assertEqual(topology_result.provider_count, 1)
        self.assertEqual(topology_result.successful_provider_count, 1)
        self.assertEqual(topology_result.errors, ())
        self.assertEqual(len(graph.resources()), 3)
        self.assertEqual(len(relations), 2)
        self.assertEqual((relations[0].source_id, relations[0].type, relations[0].target_id), (container_id, "uses_image", image_id))
        self.assertEqual((relations[1].source_id, relations[1].type, relations[1].target_id), (container_id, "connected_to", network_id))
        self.assertEqual(graph.outgoing(container_id), relations)
        self.assertEqual(graph.incoming(image_id), (relations[0],))
        self.assertEqual(graph.incoming(network_id), (relations[1],))
        self.assertEqual(tuple(resource.id for resource in graph.neighbors(container_id)), (image_id, network_id))
        self.assertEqual(relations[0].metadata["reference"], "zorix/api:latest")
        self.assertEqual(relations[1].metadata["network_name"], "backend")


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
