from __future__ import annotations

from zorix_core_model import Resource
from zorix_resource_graph import ResourceGraph, ResourceRelation
from zorix_topology_engine import TopologyProviderError, TopologyResult


class TopologyConsoleRenderer:
    def render(self, result: TopologyResult) -> str:
        graph = result.graph
        lines = _summary_lines(result)
        sections: list[list[str]] = []

        relations = graph.relations()
        if relations:
            sections.append(
                [
                    "Relations:",
                    *[self._format_relation(relation, graph) for relation in relations],
                ]
            )

        if result.errors:
            sections.append(
                ["Errors:", *[self._format_error(error) for error in result.errors]]
            )

        for section in sections:
            lines.append("")
            lines.extend(section)

        return "\n".join(lines) + "\n"

    def _format_relation(
        self,
        relation: ResourceRelation,
        graph: ResourceGraph,
    ) -> str:
        source = graph.resource(relation.source_id)
        target = graph.resource(relation.target_id)

        return (
            f"- {_resource_label(source)} "
            f"--{relation.type}--> "
            f"{_resource_label(target)}"
        )

    def _format_error(self, error: TopologyProviderError) -> str:
        message = error.message.strip()
        if message:
            return f"- {error.provider}: {error.error_type}: {message}"

        return f"- {error.provider}: {error.error_type}"


def _summary_lines(result: TopologyResult) -> list[str]:
    graph = result.graph
    lines = [
        f"Topology: {result.status.name}",
        f"Providers: {result.provider_count}",
        f"Successful providers: {result.successful_provider_count}",
        f"Failed providers: {result.failed_provider_count}",
        f"Resources: {len(graph.resources())}",
        f"Relations: {len(graph.relations())}",
    ]

    if result.errors:
        lines.append(f"Errors: {len(result.errors)}")

    return lines


def _resource_label(resource: Resource) -> str:
    return f"{_resource_type(resource)} {_resource_name(resource)}"


def _resource_type(resource: Resource) -> str:
    value = getattr(resource, "type", None)
    if isinstance(value, str):
        text = value.strip()
        if text:
            return _display_type(text)

    return type(resource).__name__


def _resource_name(resource: Resource) -> str:
    for attribute in ("name", "id"):
        value = getattr(resource, attribute, None)
        if not isinstance(value, str):
            continue

        text = value.strip()
        if text:
            return text

    return type(resource).__name__


def _display_type(value: str) -> str:
    normalized = value.replace("_", " ").replace("-", " ")
    if normalized.islower():
        return "".join(word.capitalize() for word in normalized.split())

    return value
