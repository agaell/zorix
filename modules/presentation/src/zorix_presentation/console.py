from __future__ import annotations

from dataclasses import fields, is_dataclass

from zorix_scan_engine import AdapterScanError, ScanResult, ScanStatus


class ConsoleRenderer:
    def render(
        self,
        result: ScanResult,
        *,
        adapter_count: int | None = None,
    ) -> str:
        lines = _summary_lines(result, adapter_count)
        sections: list[list[str]] = []

        if result.resources:
            sections.append(["Resources:", *[self._format_resource(resource) for resource in result.resources]])

        if result.errors:
            sections.append(["Errors:", *[self._format_error(error) for error in result.errors]])

        for section in sections:
            lines.append("")
            lines.extend(section)

        return "\n".join(lines) + "\n"

    def _format_resource(self, resource: object) -> str:
        return f"- {_resource_type(resource)}: {_display_name(resource)}"

    def _format_error(self, error: AdapterScanError) -> str:
        message = error.message.strip()
        if message:
            return f"- {error.adapter}: {error.error_type}: {message}"

        return f"- {error.adapter}: {error.error_type}"


def _summary_lines(result: ScanResult, adapter_count: int | None) -> list[str]:
    lines = [
        f"Status: {result.status.name}",
    ]

    if adapter_count is not None:
        lines.append(f"Adapters: {adapter_count}")

    lines.append(f"Resources: {len(result.resources)}")

    if result.status in (ScanStatus.PARTIAL, ScanStatus.FAILED):
        lines.append(f"Errors: {len(result.errors)}")

    return lines


def _resource_type(resource: object) -> str:
    kind = _non_empty_attribute(resource, "kind")
    if kind is not None:
        return _display_type(kind)

    resource_type = _non_empty_attribute(resource, "type")
    if resource_type is not None:
        return _display_type(resource_type)

    return type(resource).__name__


def _display_name(resource: object) -> str:
    for attribute in ("name", "id", "identifier"):
        value = _non_empty_attribute(resource, attribute)
        if value is not None:
            return value

    if is_dataclass(resource):
        dataclass_text = _dataclass_fields_text(resource)
        if dataclass_text:
            return dataclass_text
        return type(resource).__name__

    text = str(resource).strip()
    if _is_informative_text(resource, text):
        return text

    return type(resource).__name__


def _non_empty_attribute(resource: object, attribute: str) -> str | None:
    value = getattr(resource, attribute, None)
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    return text


def _dataclass_fields_text(resource: object) -> str:
    parts: list[str] = []
    for field in fields(resource):
        if field.name.startswith("_"):
            continue

        value = getattr(resource, field.name)
        parts.append(f"{field.name}={value}")

    return ", ".join(parts)


def _is_informative_text(resource: object, text: str) -> bool:
    if not text:
        return False

    default_prefix = f"<{type(resource).__module__}.{type(resource).__qualname__} object at 0x"
    return not text.startswith(default_prefix)


def _display_type(value: str) -> str:
    normalized = value.replace("_", " ").replace("-", " ")
    if normalized.islower():
        return "".join(word.capitalize() for word in normalized.split())

    return value
