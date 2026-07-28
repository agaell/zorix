from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


class _ResourceRelationSlots:
    __slots__ = ("source_id", "target_id", "type", "metadata")


@dataclass(frozen=True)
class ResourceRelation(_ResourceRelationSlots):
    __slots__ = ()

    source_id: str
    target_id: str
    type: str
    metadata: Mapping[str, str] = field(
        default_factory=dict,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _required_string(self.source_id, "source_id"))
        object.__setattr__(self, "target_id", _required_string(self.target_id, "target_id"))
        object.__setattr__(self, "type", _required_string(self.type, "type"))
        object.__setattr__(self, "metadata", _metadata_proxy(self.metadata))

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.source_id, self.type, self.target_id)


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")

    return text


def _metadata_proxy(metadata: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping")

    copied: dict[str, str] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise TypeError("metadata keys must be strings")
        if not isinstance(value, str):
            raise TypeError("metadata values must be strings")

        copied[key] = value

    return MappingProxyType(copied)
