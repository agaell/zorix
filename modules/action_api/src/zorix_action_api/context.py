from __future__ import annotations

from collections.abc import Iterable

from zorix_core_model import Resource
from zorix_resource_graph import DuplicateResourceError, UnknownResourceError


class ActionContext:
    def __init__(self, resources: Iterable[Resource]) -> None:
        self._resources = tuple(resources)
        self._resources_by_id: dict[str, Resource] = {}
        self._resources_by_type: dict[str, list[Resource]] = {}

        for resource in self._resources:
            resource_id = _resource_id(resource)
            if resource_id in self._resources_by_id:
                raise DuplicateResourceError(resource_id)

            self._resources_by_id[resource_id] = resource
            self._resources_by_type.setdefault(resource.type, []).append(resource)

    def resources(self) -> tuple[Resource, ...]:
        return self._resources

    def has_resource(self, resource_id: str) -> bool:
        normalized_id = _lookup_id(resource_id)
        return normalized_id is not None and normalized_id in self._resources_by_id

    def resource(self, resource_id: str) -> Resource:
        normalized_id = _lookup_id(resource_id)
        if normalized_id is None or normalized_id not in self._resources_by_id:
            raise UnknownResourceError(str(resource_id))

        return self._resources_by_id[normalized_id]

    def resources_by_type(self, resource_type: str) -> tuple[Resource, ...]:
        if not isinstance(resource_type, str):
            raise TypeError("resource_type must be a string")

        normalized_type = resource_type.strip()
        if not normalized_type:
            return ()

        return tuple(self._resources_by_type.get(normalized_type, ()))

    def __len__(self) -> int:
        return len(self._resources)


def _resource_id(resource: Resource) -> str:
    if not isinstance(resource, Resource):
        raise TypeError("resource must be a Resource")

    resource_id = resource.id
    if not isinstance(resource_id, str):
        raise ValueError("Resource id must be a string")

    normalized_id = resource_id.strip()
    if not normalized_id:
        raise ValueError("Resource id must not be empty")
    if normalized_id != resource_id:
        raise ValueError("Resource id must not contain external whitespace")

    return normalized_id


def _lookup_id(resource_id: str) -> str | None:
    if not isinstance(resource_id, str):
        raise TypeError("resource_id must be a string")

    normalized_id = resource_id.strip()
    if not normalized_id:
        return None

    return normalized_id
