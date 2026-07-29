from __future__ import annotations

from collections.abc import Iterable

from zorix_core_model import Resource
from zorix_resource_graph import ResourceGraph, ResourceGraphBuilder


class TopologyContext:
    def __init__(self, resources: Iterable[Resource]) -> None:
        builder = ResourceGraphBuilder()
        builder.add_resources(resources)
        self._graph = builder.build()

    def resources(self) -> tuple[Resource, ...]:
        return self._graph.resources()

    def has_resource(self, resource_id: str) -> bool:
        return self._graph.has_resource(resource_id)

    def resource(self, resource_id: str) -> Resource:
        return self._graph.resource(resource_id)

    def resources_by_type(self, resource_type: str) -> tuple[Resource, ...]:
        if not isinstance(resource_type, str):
            raise TypeError("resource_type must be a string")

        normalized_type = resource_type.strip()
        if not normalized_type:
            return ()

        return tuple(
            resource
            for resource in self._graph.resources()
            if resource.type == normalized_type
        )

    def __len__(self) -> int:
        return len(self._graph)
