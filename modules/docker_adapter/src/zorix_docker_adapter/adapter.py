from __future__ import annotations

from zorix_core_model import Adapter, Resource
from zorix_resource_graph import ResourceRelation
from zorix_topology_api import TopologyContext

from .command import DockerCommandRunner, SubprocessDockerCommandRunner
from .inventory import (
    containers_to_resources,
    images_to_resources,
    networks_to_resources,
    parse_inspect_array,
    parse_listing_ids,
)
from .topology import container_inspect_to_relations, docker_container_ids


_LIST_CONTAINER_ARGUMENTS = (
    "container",
    "ls",
    "--all",
    "--quiet",
    "--no-trunc",
)
_INSPECT_CONTAINER_ARGUMENTS = ("container", "inspect")
_LIST_IMAGE_ARGUMENTS = ("image", "ls", "--all", "--quiet", "--no-trunc")
_INSPECT_IMAGE_ARGUMENTS = ("image", "inspect")
_LIST_NETWORK_ARGUMENTS = ("network", "ls", "--quiet", "--no-trunc")
_INSPECT_NETWORK_ARGUMENTS = ("network", "inspect")


class DockerAdapter(Adapter):
    def __init__(self, runner: DockerCommandRunner | None = None) -> None:
        self._runner = runner if runner is not None else SubprocessDockerCommandRunner()

    def discover(self) -> list[Resource]:
        resources: list[Resource] = []
        resources.extend(self._discover_containers())
        resources.extend(self._discover_images())
        resources.extend(self._discover_networks())
        return resources

    def discover_relations(self, context: TopologyContext) -> list[ResourceRelation]:
        container_ids = docker_container_ids(context)
        if not container_ids:
            return []

        inspect_output = self._runner.run((*_INSPECT_CONTAINER_ARGUMENTS, *container_ids))
        return container_inspect_to_relations(inspect_output, context=context)

    def _discover_containers(self) -> list[Resource]:
        container_ids = parse_listing_ids(self._runner.run(_LIST_CONTAINER_ARGUMENTS))
        if not container_ids:
            return []

        inspect_output = self._runner.run((*_INSPECT_CONTAINER_ARGUMENTS, *container_ids))
        containers = parse_inspect_array(
            inspect_output,
            subject="docker container inspect",
        )
        return containers_to_resources(containers)

    def _discover_images(self) -> list[Resource]:
        image_ids = parse_listing_ids(self._runner.run(_LIST_IMAGE_ARGUMENTS))
        if not image_ids:
            return []

        inspect_output = self._runner.run((*_INSPECT_IMAGE_ARGUMENTS, *image_ids))
        images = parse_inspect_array(inspect_output, subject="docker image inspect")
        return images_to_resources(images)

    def _discover_networks(self) -> list[Resource]:
        network_ids = parse_listing_ids(self._runner.run(_LIST_NETWORK_ARGUMENTS))
        if not network_ids:
            return []

        inspect_output = self._runner.run((*_INSPECT_NETWORK_ARGUMENTS, *network_ids))
        networks = parse_inspect_array(inspect_output, subject="docker network inspect")
        return networks_to_resources(networks)
