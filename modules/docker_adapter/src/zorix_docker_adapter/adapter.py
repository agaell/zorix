from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

from zorix_core_model import Adapter, Resource

from .command import DockerCommandRunner, SubprocessDockerCommandRunner
from .errors import DockerOutputError


_LIST_CONTAINER_ARGUMENTS = (
    "container",
    "ls",
    "--all",
    "--quiet",
    "--no-trunc",
)
_INSPECT_CONTAINER_ARGUMENTS = ("container", "inspect")


class DockerAdapter(Adapter):
    def __init__(self, runner: DockerCommandRunner | None = None) -> None:
        self._runner = runner if runner is not None else SubprocessDockerCommandRunner()

    def discover(self) -> list[Resource]:
        list_output = self._runner.run(_LIST_CONTAINER_ARGUMENTS)
        container_ids = _container_ids(list_output)
        if not container_ids:
            return []

        inspect_output = self._runner.run((*_INSPECT_CONTAINER_ARGUMENTS, *container_ids))
        containers = _parse_inspect_output(inspect_output)
        return [_container_to_resource(container) for container in containers]


def _container_ids(output: str) -> list[str]:
    container_ids: list[str] = []
    for line in output.splitlines():
        container_id = line.strip()
        if container_id:
            container_ids.append(container_id)

    return container_ids


def _parse_inspect_output(output: str) -> list[Mapping[str, Any]]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise DockerOutputError("docker container inspect returned invalid JSON") from exc

    if not isinstance(payload, list):
        raise DockerOutputError("docker container inspect JSON must be an array")

    containers: list[Mapping[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise DockerOutputError(f"docker container inspect item {index} must be an object")
        containers.append(item)

    return containers


def _container_to_resource(container: Mapping[str, Any]) -> Resource:
    docker_id = _required_docker_id(container)

    return Resource(
        id=f"docker:container:{docker_id}",
        type="container",
        name=_container_name(container, docker_id),
        state=_container_state(container),
        metadata=_extract_metadata(container, docker_id),
        labels=_extract_labels(container),
    )


def _required_docker_id(container: Mapping[str, Any]) -> str:
    docker_id = _get_non_empty_string(container, "Id")
    if docker_id is None:
        raise DockerOutputError("docker container inspect item is missing non-empty Id")

    return docker_id


def _container_name(container: Mapping[str, Any], docker_id: str) -> str:
    name = _get_non_empty_string(container, "Name")
    if name is None:
        return docker_id[:12]

    if name.startswith("/"):
        name = name[1:]

    if not name:
        return docker_id[:12]

    return name


def _container_state(container: Mapping[str, Any]) -> str:
    state = _get_mapping(container, "State")
    return _get_non_empty_string(state, "Status") or "unknown"


def _extract_labels(container: Mapping[str, Any]) -> dict[str, str]:
    config = _get_mapping(container, "Config")
    labels = config.get("Labels")
    if not isinstance(labels, Mapping):
        return {}

    return {
        key: value
        for key, value in labels.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _extract_metadata(container: Mapping[str, Any], docker_id: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    config = _get_mapping(container, "Config")
    state = _get_mapping(container, "State")
    host_config = _get_mapping(container, "HostConfig")
    restart_policy = _get_mapping(host_config, "RestartPolicy")
    network_settings = _get_mapping(container, "NetworkSettings")
    networks = _get_mapping(network_settings, "Networks")
    health = _get_mapping(state, "Health")

    _add_metadata(metadata, "docker_id", docker_id)
    _add_metadata(metadata, "image", _get_non_empty_string(config, "Image"))
    _add_metadata(metadata, "image_id", _get_non_empty_string(container, "Image"))
    _add_metadata(metadata, "created", _get_non_empty_string(container, "Created"))
    _add_metadata(metadata, "hostname", _get_non_empty_string(config, "Hostname"))
    _add_metadata(metadata, "health", _get_non_empty_string(health, "Status"))
    _add_metadata(metadata, "restart_policy", _get_non_empty_string(restart_policy, "Name"))
    _add_metadata(metadata, "networks", _network_names(networks))

    return metadata


def _network_names(networks: Mapping[str, Any]) -> str | None:
    names = sorted(name.strip() for name in networks if isinstance(name, str) and name.strip())
    if not names:
        return None

    return ",".join(names)


def _add_metadata(metadata: dict[str, str], key: str, value: str | None) -> None:
    if value is not None:
        metadata[key] = value


def _get_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    if isinstance(value, Mapping):
        return value

    return {}


def _get_non_empty_string(mapping: Mapping[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    return text
