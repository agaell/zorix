from __future__ import annotations

from typing import Protocol, runtime_checkable

from zorix_resource_graph import ResourceRelation

from .context import TopologyContext


@runtime_checkable
class TopologyProvider(Protocol):
    def discover_relations(
        self,
        context: TopologyContext,
    ) -> list[ResourceRelation]:
        ...
