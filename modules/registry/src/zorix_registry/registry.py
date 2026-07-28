from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from zorix_core_model import Adapter, Resource


class DuplicateAdapterError(ValueError):
    pass


class Registry:
    def __init__(self) -> None:
        self._adapters: dict[type[Adapter], Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        adapter_type = _adapter_type(adapter)
        if adapter_type in self._adapters:
            raise DuplicateAdapterError(f"adapter already registered: {_class_name(adapter_type)}")

        self._adapters[adapter_type] = adapter

    def register_many(self, adapters: Iterable[Adapter]) -> None:
        adapter_list = list(adapters)
        adapter_types: set[type[Adapter]] = set()
        validated_adapters: list[tuple[type[Adapter], Adapter]] = []

        for adapter in adapter_list:
            adapter_type = _adapter_type(adapter)

            if adapter_type in self._adapters:
                raise DuplicateAdapterError(f"adapter already registered: {_class_name(adapter_type)}")

            if adapter_type in adapter_types:
                raise DuplicateAdapterError(f"duplicate adapter in input: {_class_name(adapter_type)}")

            adapter_types.add(adapter_type)
            validated_adapters.append((adapter_type, adapter))

        for adapter_type, adapter in validated_adapters:
            self._adapters[adapter_type] = adapter

    def adapters(self) -> tuple[Adapter, ...]:
        return tuple(self._adapters.values())

    def scan(self) -> list[Resource]:
        resources: list[Resource] = []
        for adapter in self._adapters.values():
            resources.extend(adapter.discover())
        return resources

    def clear(self) -> None:
        self._adapters.clear()


def _adapter_type(adapter: Adapter) -> type[Adapter]:
    if not isinstance(adapter, Adapter):
        raise TypeError("adapter must implement Adapter")

    return cast(type[Adapter], type(adapter))


def _class_name(adapter_type: type[Adapter]) -> str:
    return f"{adapter_type.__module__}.{adapter_type.__qualname__}"
