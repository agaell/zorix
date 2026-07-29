from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from zorix_resource_graph import ResourceRelation
from zorix_topology_api import TopologyContext

from .errors import DockerOutputError
from .inventory import parse_inspect_array


CONTAINER_RESOURCE_PREFIX = "docker:container:"
_DOCKER_CONTAINER_ID_LENGTH = 64
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def docker_container_ids(context: TopologyContext) -> list[str]:
    docker_ids: list[str] = []
    seen: set[str] = set()

    for resource in context.resources():
        if resource.type != "container" or not resource.id.startswith(CONTAINER_RESOURCE_PREFIX):
            continue

        docker_id = _validated_container_id(resource.id)
        if docker_id in seen:
            continue

        seen.add(docker_id)
        docker_ids.append(docker_id)

    return docker_ids


def _validated_container_id(resource_id: str) -> str:
    docker_id = resource_id[len(CONTAINER_RESOURCE_PREFIX) :]
    if (
        len(docker_id) != _DOCKER_CONTAINER_ID_LENGTH
        or any(character not in _HEX_DIGITS for character in docker_id)
    ):
        raise DockerOutputError(
            "docker container resource id must contain a full 64-character hex Docker ID"
        )

    return docker_id


def container_inspect_to_relations(
    output: str,
    *,
    context: TopologyContext,
) -> list[ResourceRelation]:
    containers = parse_inspect_array(output, subject="docker container inspect")
    containers_by_id = _containers_by_id(containers)
    relations: list[ResourceRelation] = []
    seen: set[tuple[str, str, str]] = set()

    for docker_id in docker_container_ids(context):
        container = containers_by_id.get(docker_id)
        if container is None:
            continue

        _append_relation(relations, seen, _uses_image_relation(container, context))
        for relation in _connected_to_relations(container, context):
            _append_relation(relations, seen, relation)

    return relations


def _containers_by_id(
    containers: list[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    containers_by_id: dict[str, Mapping[str, object]] = {}

    for container in containers:
        docker_id = _required_docker_id(container)
        containers_by_id.setdefault(docker_id, container)

    return containers_by_id


def _required_docker_id(container: Mapping[str, object]) -> str:
    docker_id = _non_empty_string(container, "Id")
    if docker_id is None:
        raise DockerOutputError("docker container inspect item is missing non-empty Id")

    return docker_id


def _uses_image_relation(
    container: Mapping[str, object],
    context: TopologyContext,
) -> ResourceRelation | None:
    docker_id = _required_docker_id(container)
    image_id = _non_empty_string(container, "Image")
    if image_id is None:
        return None

    source_id = f"docker:container:{docker_id}"
    target_id = f"docker:image:{image_id}"
    if not context.has_resource(source_id) or not context.has_resource(target_id):
        return None

    metadata: dict[str, str] = {}
    reference = _non_empty_string(_mapping_value(container, "Config"), "Image")
    if reference is not None:
        metadata["reference"] = reference

    return ResourceRelation(
        source_id=source_id,
        target_id=target_id,
        type="uses_image",
        metadata=metadata,
    )


def _connected_to_relations(
    container: Mapping[str, object],
    context: TopologyContext,
) -> list[ResourceRelation]:
    docker_id = _required_docker_id(container)
    source_id = f"docker:container:{docker_id}"
    if not context.has_resource(source_id):
        return []

    networks = _mapping_value(_mapping_value(container, "NetworkSettings"), "Networks")
    relations: list[ResourceRelation] = []

    for network_name, endpoint in networks.items():
        if not isinstance(endpoint, Mapping):
            continue

        endpoint_mapping = cast(Mapping[str, object], endpoint)
        network_id = _non_empty_string(endpoint_mapping, "NetworkID")
        if network_id is None:
            continue

        target_id = f"docker:network:{network_id}"
        if not context.has_resource(target_id):
            continue

        metadata = _network_metadata(network_name, endpoint_mapping)
        relations.append(
            ResourceRelation(
                source_id=source_id,
                target_id=target_id,
                type="connected_to",
                metadata=metadata,
            )
        )

    return relations


def _network_metadata(
    network_name: object,
    endpoint: Mapping[str, object],
) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if isinstance(network_name, str):
        name = network_name.strip()
        if name:
            metadata["network_name"] = name

    _add_metadata(metadata, "ipv4_address", _non_empty_string(endpoint, "IPAddress"))
    _add_metadata(metadata, "ipv6_address", _non_empty_string(endpoint, "GlobalIPv6Address"))
    _add_metadata(metadata, "mac_address", _non_empty_string(endpoint, "MacAddress"))

    return metadata


def _append_relation(
    relations: list[ResourceRelation],
    seen: set[tuple[str, str, str]],
    relation: ResourceRelation | None,
) -> None:
    if relation is None or relation.identity in seen:
        return

    seen.add(relation.identity)
    relations.append(relation)


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


def _add_metadata(metadata: dict[str, str], key: str, value: str | None) -> None:
    if value is not None:
        metadata[key] = value
