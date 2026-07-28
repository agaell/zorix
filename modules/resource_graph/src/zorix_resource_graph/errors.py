from __future__ import annotations

from .relation import ResourceRelation


class ResourceGraphError(RuntimeError):
    pass


class DuplicateResourceError(ResourceGraphError):
    def __init__(self, resource_id: str) -> None:
        self.resource_id = resource_id
        super().__init__(f"Resource is already registered in graph: {resource_id}")


class DuplicateRelationError(ResourceGraphError):
    def __init__(self, identity: tuple[str, str, str]) -> None:
        self.identity = identity
        source_id, relation_type, target_id = identity
        super().__init__(
            f"Resource relation is already registered: {source_id} --{relation_type}--> {target_id}"
        )


class UnknownResourceError(ResourceGraphError):
    def __init__(self, resource_id: str) -> None:
        self.resource_id = resource_id
        super().__init__(f"Resource is not registered in graph: {resource_id}")


class InvalidRelationError(ResourceGraphError):
    def __init__(
        self,
        relation: ResourceRelation,
        missing_resource_ids: tuple[str, ...],
    ) -> None:
        self.relation = relation
        self.missing_resource_ids = missing_resource_ids
        missing = ", ".join(missing_resource_ids)
        super().__init__(f"Resource relation references unknown resources: {missing}")
