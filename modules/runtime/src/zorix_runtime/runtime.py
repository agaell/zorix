from __future__ import annotations

from pathlib import Path

from zorix_core_model import Adapter
from zorix_plugin_loader import PluginLoader
from zorix_registry import Registry
from zorix_scan_engine import ScanEngine, ScanResult


class ZorixRuntime:
    def __init__(
        self,
        plugin_loader: PluginLoader | None = None,
        registry: Registry | None = None,
    ) -> None:
        self._plugin_loader = plugin_loader if plugin_loader is not None else PluginLoader()
        self._registry = registry if registry is not None else Registry()
        self._scan_engine = ScanEngine(self._registry)

    def load_plugins(self, path: str | Path) -> tuple[Adapter, ...]:
        adapters = tuple(self._plugin_loader.load(path))
        self._registry.register_many(adapters)
        return adapters

    def scan(self, *, continue_on_error: bool = False) -> ScanResult:
        return self._scan_engine.scan(continue_on_error=continue_on_error)

    def adapters(self) -> tuple[Adapter, ...]:
        return self._registry.adapters()

    def clear(self) -> None:
        self._registry.clear()
