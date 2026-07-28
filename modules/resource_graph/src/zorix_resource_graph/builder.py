from __future__ import annotations

from collections.abc import Iterable

from zorix_core_model import Resource

from .errors import (
    DuplicateRelationError,
    DuplicateResourceError,
    InvalidRelationError,
)
from .graph import ResourceGraph
from .relation import ResourceRelation


class ResourceGraphBuilder:
    def __init__(self) -> None:
        self._resources: list[Resource] = []
        self._resource_ids: set[str] = set()
        self._relations: list[ResourceRelation] = []
        self._relation_identities: set[tuple[str, str, str]] = set()

    def add_resource(self, resource: Resource) -> None:
        resource_id = _resource_id(resource)
        if resource_id in self._resource_ids:
            raise DuplicateResourceError(resource_id)

        self._resources.append(resource)
        self._resource_ids.add(resource_id)

    def add_resources(self, resources: Iterable[Resource]) -> None:
        resource_list = list(resources)
        validated_resources: list[tuple[str, Resource]] = []
        batch_resource_ids: set[str] = set()

        for resource in resource_list:
            resource_id = _resource_id(resource)
            if resource_id in self._resource_ids or resource_id in batch_resource_ids:
                raise DuplicateResourceError(resource_id)

            batch_resource_ids.add(resource_id)
            validated_resources.append((resource_id, resource))

        for resource_id, resource in validated_resources:
            self._resources.append(resource)
            self._resource_ids.add(resource_id)

    def add_relation(self, relation: ResourceRelation) -> None:
        self._validate_relation_type(relation)
        missing_resource_ids = _missing_resource_ids(self._resource_ids, relation)
        if missing_resource_ids:
            raise InvalidRelationError(relation, missing_resource_ids)

        if relation.identity in self._relation_identities:
            raise DuplicateRelationError(relation.identity)

        self._relations.append(relation)
        self._relation_identities.add(relation.identity)

    def add_relations(self, relations: Iterable[ResourceRelation]) -> None:
        relation_list = list(relations)
        validated_relations: list[ResourceRelation] = []
        batch_identities: set[tuple[str, str, str]] = set()

        for relation in relation_list:
            self._validate_relation_type(relation)
            missing_resource_ids = _missing_resource_ids(self._resource_ids, relation)
            if missing_resource_ids:
                raise InvalidRelationError(relation, missing_resource_ids)

            if (
                relation.identity in self._relation_identities
                or relation.identity in batch_identities
            ):
                raise DuplicateRelationError(relation.identity)

            batch_identities.add(relation.identity)
            validated_relations.append(relation)

        for relation in validated_relations:
            self._relations.append(relation)
            self._relation_identities.add(relation.identity)

    def build(self) -> ResourceGraph:
        return ResourceGraph(tuple(self._resources), tuple(self._relations))

    def clear(self) -> None:
        self._resources.clear()
        self._resource_ids.clear()
        self._relations.clear()
        self._relation_identities.clear()

    def _validate_relation_type(self, relation: ResourceRelation) -> None:
        if not isinstance(relation, ResourceRelation):
            raise TypeError("relation must be a ResourceRelation")


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
