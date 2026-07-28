from __future__ import annotations

from zorix_core_model import Resource

from .errors import (
    DuplicateRelationError,
    DuplicateResourceError,
    InvalidRelationError,
    UnknownResourceError,
)
from .relation import ResourceRelation


class ResourceGraph:
    def __init__(
        self,
        resources: tuple[Resource, ...],
        relations: tuple[ResourceRelation, ...],
    ) -> None:
        self._resources = tuple(resources)
        self._relations = tuple(relations)
        self._resources_by_id: dict[str, Resource] = {}
        self._outgoing: dict[str, list[ResourceRelation]] = {}
        self._incoming: dict[str, list[ResourceRelation]] = {}

        for resource in self._resources:
            resource_id = _resource_id(resource)
            if resource_id in self._resources_by_id:
                raise DuplicateResourceError(resource_id)

            self._resources_by_id[resource_id] = resource
            self._outgoing[resource_id] = []
            self._incoming[resource_id] = []

        relation_identities: set[tuple[str, str, str]] = set()
        resource_ids = set(self._resources_by_id)
        for relation in self._relations:
            missing_resource_ids = _missing_resource_ids(resource_ids, relation)
            if missing_resource_ids:
                raise InvalidRelationError(relation, missing_resource_ids)

            if relation.identity in relation_identities:
                raise DuplicateRelationError(relation.identity)

            relation_identities.add(relation.identity)
            self._outgoing[relation.source_id].append(relation)
            self._incoming[relation.target_id].append(relation)

    def resources(self) -> tuple[Resource, ...]:
        return self._resources

    def relations(self) -> tuple[ResourceRelation, ...]:
        return self._relations

    def has_resource(self, resource_id: str) -> bool:
        normalized_id = _lookup_id(resource_id)
        return normalized_id is not None and normalized_id in self._resources_by_id

    def resource(self, resource_id: str) -> Resource:
        normalized_id = self._known_resource_id(resource_id)
        return self._resources_by_id[normalized_id]

    def outgoing(
        self,
        resource_id: str,
        *,
        relation_type: str | None = None,
    ) -> tuple[ResourceRelation, ...]:
        normalized_id = self._known_resource_id(resource_id)
        return _filter_relations(self._outgoing[normalized_id], relation_type)

    def incoming(
        self,
        resource_id: str,
        *,
        relation_type: str | None = None,
    ) -> tuple[ResourceRelation, ...]:
        normalized_id = self._known_resource_id(resource_id)
        return _filter_relations(self._incoming[normalized_id], relation_type)

    def neighbors(
        self,
        resource_id: str,
        *,
        relation_type: str | None = None,
    ) -> tuple[Resource, ...]:
        normalized_id = self._known_resource_id(resource_id)
        normalized_type = _relation_type_filter(relation_type)
        neighbors: list[Resource] = []
        seen_resource_ids: set[str] = set()

        for relation in self._relations:
            if normalized_type is not None and relation.type != normalized_type:
                continue

            if relation.source_id == normalized_id:
                _append_neighbor(
                    neighbors,
                    seen_resource_ids,
                    relation.target_id,
                    self._resources_by_id,
                )

            if relation.target_id == normalized_id:
                _append_neighbor(
                    neighbors,
                    seen_resource_ids,
                    relation.source_id,
                    self._resources_by_id,
                )

        return tuple(neighbors)

    def __len__(self) -> int:
        return len(self._resources)

    def _known_resource_id(self, resource_id: str) -> str:
        normalized_id = _lookup_id(resource_id)
        if normalized_id is None or normalized_id not in self._resources_by_id:
            raise UnknownResourceError(_unknown_resource_id(resource_id))

        return normalized_id


def _filter_relations(
    relations: list[ResourceRelation],
    relation_type: str | None,
) -> tuple[ResourceRelation, ...]:
    normalized_type = _relation_type_filter(relation_type)
    if normalized_type is None:
        return tuple(relations)

    return tuple(relation for relation in relations if relation.type == normalized_type)


def _append_neighbor(
    neighbors: list[Resource],
    seen_resource_ids: set[str],
    resource_id: str,
    resources_by_id: dict[str, Resource],
) -> None:
    if resource_id in seen_resource_ids:
        return

    seen_resource_ids.add(resource_id)
    neighbors.append(resources_by_id[resource_id])


def _missing_resource_ids(
    resource_ids: set[str],
    relation: ResourceRelation,
) -> tuple[str, ...]:
    missing: list[str] = []

    if relation.source_id not in resource_ids:
        missing.append(relation.source_id)

    if relation.target_id not in resource_ids and relation.target_id != relation.source_id:
        missing.append(relation.target_id)

    return tuple(missing)


def _resource_id(resource: Resource) -> str:
    resource_id = getattr(resource, "id", None)
    if not isinstance(resource_id, str):
        raise ValueError("Resource id must be a string")

    normalized_id = resource_id.strip()
    if not normalized_id:
        raise ValueError("Resource id must not be empty")

    if normalized_id != resource_id:
        raise ValueError("Resource id must not contain external whitespace")

    return normalized_id


def _lookup_id(resource_id: object) -> str | None:
    if not isinstance(resource_id, str):
        return None

    normalized_id = resource_id.strip()
    if not normalized_id:
        return None

    return normalized_id


def _unknown_resource_id(resource_id: object) -> str:
    if isinstance(resource_id, str):
        return resource_id.strip()

    return ""


def _relation_type_filter(relation_type: str | None) -> str | None:
    if relation_type is None:
        return None

    if not isinstance(relation_type, str):
        raise TypeError("relation_type must be a string or None")

    return relation_type.strip()
