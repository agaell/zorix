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
    relations: list[ResourceRelation] = []

    for resource in context.resources():
        if resource.type != "service":
            continue
        if not resource.id.startswith(service_prefix):
            continue
        if resource.metadata.get("host_id") != host_id:
            continue
        if not context.has_resource(resource.id):
            continue

        relations.append(
            ResourceRelation(
                source_id=host_id,
                target_id=resource.id,
                type="hosts",
            )
        )

    return relations
