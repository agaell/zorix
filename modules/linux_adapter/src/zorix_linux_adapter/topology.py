from __future__ import annotations

from zorix_resource_graph import ResourceRelation
from zorix_topology_api import TopologyContext

from .inventory import host_resource_id


def host_to_service_relations(
    *,
    target: str,
    context: TopologyContext,
) -> list[ResourceRelation]:
    host_id = host_resource_id(target)
    if not context.has_resource(host_id):
        return []

    service_prefix = f"linux:service:{target}:"
    filesystem_prefix = f"linux:filesystem:{target}:"
    socket_prefix = f"linux:socket:{target}:"
    relations: list[ResourceRelation] = []

    for resource in context.resources():
        relation_type = _relation_type_for(
            resource_type=resource.type,
            resource_id=resource.id,
            host_id=host_id,
            service_prefix=service_prefix,
            filesystem_prefix=filesystem_prefix,
            socket_prefix=socket_prefix,
            target=target,
            metadata=resource.metadata,
        )
        if relation_type is None or not context.has_resource(resource.id):
            continue

        relations.append(
            ResourceRelation(
                source_id=host_id,
                target_id=resource.id,
                type=relation_type,
            )
        )

    return relations


def _relation_type_for(
    *,
    resource_type: str,
    resource_id: str,
    host_id: str,
    service_prefix: str,
    filesystem_prefix: str,
    socket_prefix: str,
    target: str,
    metadata: dict[str, object],
) -> str | None:
    if resource_type == "service":
        if resource_id.startswith(service_prefix) and metadata.get("host_id") == host_id:
            return "hosts"
        return None

    if resource_type == "memory":
        if resource_id == f"linux:memory:{target}" and metadata.get("host_id") == host_id:
            return "has_memory"
        return None

    if resource_type == "filesystem":
        if resource_id.startswith(filesystem_prefix) and metadata.get("host_id") == host_id:
            return "mounts"
        return None

    if resource_type == "socket":
        if resource_id.startswith(socket_prefix) and metadata.get("host_id") == host_id:
            return "listens_on"
        return None

    return None
