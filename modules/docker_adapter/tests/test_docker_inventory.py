from __future__ import annotations

import copy
import json
from typing import Any
import unittest

from zorix_docker_adapter import DockerOutputError
from zorix_docker_adapter.inventory import (
    images_to_resources,
    networks_to_resources,
    parse_inspect_array,
    parse_listing_ids,
)


IMAGE_ID = "sha256:" + "b" * 64
NETWORK_ID = "c" * 64


class DockerInventoryTest(unittest.TestCase):
    def test_parse_listing_ids_strips_skips_deduplicates_and_preserves_order(self) -> None:
        self.assertEqual(
            parse_listing_ids("\n one \n\ntwo\none\n three \n"),
            ["one", "two", "three"],
        )

    def test_parse_inspect_array_rejects_invalid_json(self) -> None:
        with self.assertRaisesRegex(
            DockerOutputError,
            "docker image inspect returned invalid JSON",
        ):
            parse_inspect_array("not-json", subject="docker image inspect")

    def test_parse_inspect_array_requires_array(self) -> None:
        with self.assertRaisesRegex(
            DockerOutputError,
            "docker image inspect JSON must be an array",
        ):
            parse_inspect_array(json.dumps({"Id": IMAGE_ID}), subject="docker image inspect")

    def test_parse_inspect_array_requires_object_items(self) -> None:
        with self.assertRaisesRegex(
            DockerOutputError,
            "docker network inspect item 2 must be an object",
        ):
            parse_inspect_array(json.dumps([{"Id": NETWORK_ID}, 1]), subject="docker network inspect")

    def test_image_resource_mapping(self) -> None:
        resource = images_to_resources([_image_payload()])[0]

        self.assertEqual(resource.id, f"docker:image:{IMAGE_ID}")
        self.assertEqual(resource.type, "image")
        self.assertEqual(resource.name, "zorix/api:latest")
        self.assertEqual(resource.state, "present")
        self.assertEqual(resource.labels, {"label": "value"})
        self.assertEqual(resource.metadata["docker_id"], IMAGE_ID)
        self.assertEqual(resource.metadata["created"], "2026-07-29T09:00:00Z")
        self.assertEqual(resource.metadata["architecture"], "arm64")
        self.assertEqual(resource.metadata["os"], "linux")
        self.assertEqual(resource.metadata["variant"], "v8")
        self.assertEqual(resource.metadata["size_bytes"], "123")
        self.assertEqual(
            resource.metadata["repo_tags"],
            "zorix/api:latest,zorix/api:1.0,<none>:<none>",
        )
        self.assertEqual(resource.metadata["repo_digests"], "zorix/api@sha256:digest")

    def test_image_name_skips_none_tag_and_falls_back_to_short_id(self) -> None:
        resource = images_to_resources(
            [
                {
                    "Id": IMAGE_ID,
                    "RepoTags": [" <none>:<none> ", "", 12],
                    "Config": {"Labels": None},
                }
            ]
        )[0]

        self.assertEqual(resource.name, IMAGE_ID.removeprefix("sha256:")[:12])
        self.assertEqual(resource.labels, {})

    def test_image_full_sha256_id_is_preserved(self) -> None:
        resource = images_to_resources([_image_payload()])[0]

        self.assertEqual(resource.id, f"docker:image:{IMAGE_ID}")

    def test_image_malformed_labels_and_bool_size_are_skipped(self) -> None:
        resource = images_to_resources(
            [
                {
                    **_image_payload(),
                    "Size": True,
                    "Config": {"Labels": {"ok": "yes", "bad": 1, 2: "ignored"}},
                }
            ]
        )[0]

        self.assertEqual(resource.labels, {"ok": "yes"})
        self.assertNotIn("size_bytes", resource.metadata)

    def test_image_missing_id_raises_output_error(self) -> None:
        with self.assertRaises(DockerOutputError):
            images_to_resources([{"RepoTags": ["zorix/api:latest"]}])

    def test_image_payload_is_not_mutated(self) -> None:
        payload = [_image_payload()]
        before = copy.deepcopy(payload)

        images_to_resources(payload)

        self.assertEqual(payload, before)

    def test_network_resource_mapping(self) -> None:
        resource = networks_to_resources([_network_payload()])[0]

        self.assertEqual(resource.id, f"docker:network:{NETWORK_ID}")
        self.assertEqual(resource.type, "network")
        self.assertEqual(resource.name, "backend")
        self.assertEqual(resource.state, "present")
        self.assertEqual(resource.labels, {"network": "backend"})
        self.assertEqual(resource.metadata["docker_id"], NETWORK_ID)
        self.assertEqual(resource.metadata["driver"], "bridge")
        self.assertEqual(resource.metadata["scope"], "local")
        self.assertEqual(resource.metadata["internal"], "false")
        self.assertEqual(resource.metadata["attachable"], "true")
        self.assertEqual(resource.metadata["ingress"], "false")
        self.assertEqual(resource.metadata["ipv6"], "true")
        self.assertEqual(resource.metadata["ipam_driver"], "default")
        self.assertEqual(resource.metadata["subnets"], "172.18.0.0/16,fd00::/64")
        self.assertEqual(resource.metadata["gateways"], "172.18.0.1,fd00::1")

    def test_network_missing_name_uses_short_id(self) -> None:
        resource = networks_to_resources([{"Id": NETWORK_ID, "Name": " "}])[0]

        self.assertEqual(resource.name, NETWORK_ID[:12])

    def test_network_malformed_ipam_does_not_break_parsing(self) -> None:
        resource = networks_to_resources(
            [{"Id": NETWORK_ID, "IPAM": {"Driver": "default", "Config": "bad"}}]
        )[0]

        self.assertEqual(resource.metadata["ipam_driver"], "default")
        self.assertNotIn("subnets", resource.metadata)
        self.assertNotIn("gateways", resource.metadata)

    def test_network_missing_id_raises_output_error(self) -> None:
        with self.assertRaises(DockerOutputError):
            networks_to_resources([{"Name": "backend"}])

    def test_network_payload_is_not_mutated(self) -> None:
        payload = [_network_payload()]
        before = copy.deepcopy(payload)

        networks_to_resources(payload)

        self.assertEqual(payload, before)


def _image_payload() -> dict[str, Any]:
    return {
        "Id": IMAGE_ID,
        "RepoTags": [
            "zorix/api:latest",
            "zorix/api:latest",
            "zorix/api:1.0",
            "<none>:<none>",
        ],
        "RepoDigests": ["zorix/api@sha256:digest", "zorix/api@sha256:digest"],
        "Created": "2026-07-29T09:00:00Z",
        "Architecture": "arm64",
        "Os": "linux",
        "Variant": "v8",
        "Size": 123,
        "Config": {"Labels": {"label": "value"}},
    }


def _network_payload() -> dict[str, Any]:
    return {
        "Id": NETWORK_ID,
        "Name": "backend",
        "Driver": "bridge",
        "Scope": "local",
        "Created": "2026-07-29T08:00:00Z",
        "Internal": False,
        "Attachable": True,
        "Ingress": False,
        "EnableIPv6": True,
        "Labels": {"network": "backend", "bad": 1, 2: "ignored"},
        "IPAM": {
            "Driver": "default",
            "Config": [
                {"Subnet": "172.18.0.0/16", "Gateway": "172.18.0.1"},
                {"Subnet": "172.18.0.0/16", "Gateway": "172.18.0.1"},
                {"Subnet": "fd00::/64", "Gateway": "fd00::1"},
                "bad",
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
