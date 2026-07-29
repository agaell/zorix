from __future__ import annotations

from collections.abc import Mapping
import json
from typing import cast

from zorix_core_model import Resource

from .errors import DockerOutputError


def parse_listing_ids(output: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    for line in output.splitlines():
        item_id = line.strip()
        if not item_id or item_id in seen:
            continue

        seen.add(item_id)
        ids.append(item_id)

    return ids


def parse_inspect_array(
    output: str,
    *,
    subject: str,
) -> list[Mapping[str, object]]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise DockerOutputError(f"{subject} returned invalid JSON") from exc

    if not isinstance(payload, list):
        raise DockerOutputError(f"{subject} JSON must be an array")

    items: list[Mapping[str, object]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, Mapping):
            raise DockerOutputError(f"{subject} item {index} must be an object")

        items.append(cast(Mapping[str, object], item))

    return items


def containers_to_resources(containers: list[Mapping[str, object]]) -> list[Resource]:
    return [_container_to_resource(container) for container in containers]


def images_to_resources(images: list[Mapping[str, object]]) -> list[Resource]:
    return [_image_to_resource(image) for image in images]


def networks_to_resources(networks: list[Mapping[str, object]]) -> list[Resource]:
    return [_network_to_resource(network) for network in networks]


def _container_to_resource(container: Mapping[str, object]) -> Resource:
    docker_id = _required_docker_id(container, "container")

    return Resource(
        id=f"docker:container:{docker_id}",
        type="container",
        name=_container_name(container, docker_id),
        state=_container_state(container),
        metadata=_container_metadata(container, docker_id),
        labels=_labels(_mapping_value(_mapping_value(container, "Config"), "Labels")),
    )


def _image_to_resource(image: Mapping[str, object]) -> Resource:
    docker_id = _required_docker_id(image, "image")

    return Resource(
        id=f"docker:image:{docker_id}",
        type="image",
        name=_image_name(image, docker_id),
        state="present",
        metadata=_image_metadata(image, docker_id),
        labels=_labels(_mapping_value(_mapping_value(image, "Config"), "Labels")),
    )


def _network_to_resource(network: Mapping[str, object]) -> Resource:
    docker_id = _required_docker_id(network, "network")

    return Resource(
        id=f"docker:network:{docker_id}",
        type="network",
        name=_non_empty_string(network, "Name") or docker_id[:12],
        state="present",
        metadata=_network_metadata(network, docker_id),
        labels=_labels(network.get("Labels")),
    )


def _required_docker_id(item: Mapping[str, object], resource_type: str) -> str:
    docker_id = _non_empty_string(item, "Id")
    if docker_id is None:
        raise DockerOutputError(
            f"docker {resource_type} inspect item is missing non-empty Id"
        )

    return docker_id


def _container_name(container: Mapping[str, object], docker_id: str) -> str:
    name = _non_empty_string(container, "Name")
    if name is None:
        return docker_id[:12]

    if name.startswith("/"):
        name = name[1:]

    return name or docker_id[:12]


def _container_state(container: Mapping[str, object]) -> str:
    return _non_empty_string(_mapping_value(container, "State"), "Status") or "unknown"


def _container_metadata(container: Mapping[str, object], docker_id: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    config = _mapping_value(container, "Config")
    state = _mapping_value(container, "State")
    host_config = _mapping_value(container, "HostConfig")
    restart_policy = _mapping_value(host_config, "RestartPolicy")
    network_settings = _mapping_value(container, "NetworkSettings")
    networks = _mapping_value(network_settings, "Networks")
    health = _mapping_value(state, "Health")

    _add_metadata(metadata, "docker_id", docker_id)
    _add_metadata(metadata, "image", _non_empty_string(config, "Image"))
    _add_metadata(metadata, "image_id", _non_empty_string(container, "Image"))
    _add_metadata(metadata, "created", _non_empty_string(container, "Created"))
    _add_metadata(metadata, "hostname", _non_empty_string(config, "Hostname"))
    _add_metadata(metadata, "health", _non_empty_string(health, "Status"))
    _add_metadata(metadata, "restart_policy", _non_empty_string(restart_policy, "Name"))
    _add_metadata(metadata, "networks", _network_names(networks))

    return metadata


def _image_name(image: Mapping[str, object], docker_id: str) -> str:
    for tag in _string_list(image.get("RepoTags")):
        if tag != "<none>:<none>":
            return tag

    short_id = docker_id
    if short_id.startswith("sha256:"):
        short_id = short_id[len("sha256:") :]

    return short_id[:12]


def _image_metadata(image: Mapping[str, object], docker_id: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    _add_metadata(metadata, "docker_id", docker_id)
    _add_metadata(metadata, "created", _non_empty_string(image, "Created"))
    _add_metadata(metadata, "architecture", _non_empty_string(image, "Architecture"))
    _add_metadata(metadata, "os", _non_empty_string(image, "Os"))
    _add_metadata(metadata, "variant", _non_empty_string(image, "Variant"))
    _add_metadata(metadata, "size_bytes", _integer_string(image.get("Size")))
    _add_metadata(metadata, "repo_tags", _joined_unique_strings(image.get("RepoTags")))
    _add_metadata(metadata, "repo_digests", _joined_unique_strings(image.get("RepoDigests")))

    return metadata


def _network_metadata(network: Mapping[str, object], docker_id: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    ipam = _mapping_value(network, "IPAM")

    _add_metadata(metadata, "docker_id", docker_id)
    _add_metadata(metadata, "driver", _non_empty_string(network, "Driver"))
    _add_metadata(metadata, "scope", _non_empty_string(network, "Scope"))
    _add_metadata(metadata, "created", _non_empty_string(network, "Created"))
    _add_metadata(metadata, "internal", _bool_string(network.get("Internal")))
    _add_metadata(metadata, "attachable", _bool_string(network.get("Attachable")))
    _add_metadata(metadata, "ingress", _bool_string(network.get("Ingress")))
    _add_metadata(metadata, "ipv6", _bool_string(network.get("EnableIPv6")))
    _add_metadata(metadata, "ipam_driver", _non_empty_string(ipam, "Driver"))
    _add_metadata(metadata, "subnets", _ipam_values(ipam.get("Config"), "Subnet"))
    _add_metadata(metadata, "gateways", _ipam_values(ipam.get("Config"), "Gateway"))

    return metadata


def _labels(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}

    return {
        key: label
        for key, label in value.items()
        if isinstance(key, str) and isinstance(label, str)
    }


def _network_names(networks: Mapping[str, object]) -> str | None:
    names = sorted(name.strip() for name in networks if isinstance(name, str) and name.strip())
    if not names:
        return None

    return ",".join(names)


def _ipam_values(value: object, key: str) -> str | None:
    if not isinstance(value, list):
        return None

    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            continue

        text = _non_empty_string(cast(Mapping[str, object], item), key)
        if text is None or text in seen:
            continue

        seen.add(text)
        values.append(text)

    if not values:
        return None

    return ",".join(values)


def _joined_unique_strings(value: object) -> str | None:
    values = _string_list(value)
    if not values:
        return None

    return ",".join(values)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue

        text = item.strip()
        if not text or text in seen:
            continue

        seen.add(text)
        values.append(text)

    return values


def _mapping_value(mapping: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = mapping.get(key)
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)

    return {}


def _non_empty_string(mapping: Mapping[str, object], key: str) -> str | None:
    value = mapping.get(key)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    return text


def _integer_string(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None

    return str(value)


def _bool_string(value: object) -> str | None:
    if value is True:
        return "true"
    if value is False:
        return "false"

    return None


def _add_metadata(metadata: dict[str, str], key: str, value: str | None) -> None:
    if value is not None:
        metadata[key] = value
