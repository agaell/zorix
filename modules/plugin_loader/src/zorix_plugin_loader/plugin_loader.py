from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import inspect
from pathlib import Path
import sys
from types import ModuleType
from typing import Iterator

from zorix_core_model import Adapter


class PluginLoader:
    def load(self, path: str | Path) -> list[Adapter]:
        root = Path(path)
        if not root.is_dir():
            raise NotADirectoryError(root)

        adapters: list[Adapter] = []
        loaded_classes: set[tuple[str, str]] = set()

        with _temporary_python_paths(_python_paths_for(root)):
            for package_dir in _adapter_packages(root):
                module = _import_package(package_dir)

                for adapter_class in _exported_adapter_classes(module):
                    if inspect.isabstract(adapter_class):
                        continue

                    class_key = (adapter_class.__module__, adapter_class.__qualname__)
                    if class_key in loaded_classes:
                        continue

                    loaded_classes.add(class_key)
                    adapters.append(adapter_class())

        return adapters


def _adapter_packages(root: Path) -> list[Path]:
    candidates: list[Path] = []

    if (root / "__init__.py").is_file():
        candidates.append(root)

    src_dir = root / "src"
    if src_dir.is_dir():
        candidates.extend(_packages_in(src_dir))

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue

        if (child / "__init__.py").is_file():
            candidates.append(child)

        child_src_dir = child / "src"
        if child_src_dir.is_dir():
            candidates.extend(_packages_in(child_src_dir))

    return _unique_paths(candidates)


def _packages_in(path: Path) -> list[Path]:
    return [
        child
        for child in sorted(path.iterdir())
        if child.is_dir() and (child / "__init__.py").is_file()
    ]


def _import_package(package_dir: Path) -> ModuleType:
    init_file = package_dir / "__init__.py"
    module_name = package_dir.name
    existing_module = sys.modules.get(module_name)

    if existing_module is not None:
        existing_file = getattr(existing_module, "__file__", None)
        if existing_file is not None and Path(existing_file).resolve() == init_file.resolve():
            return existing_module
        return _import_package_with_unique_name(package_dir)

    try:
        importlib.invalidate_caches()
        return importlib.import_module(module_name)
    except Exception as exc:
        if sys.modules.get(module_name) is not existing_module:
            sys.modules.pop(module_name, None)
        raise ImportError(f"Cannot import adapter package from {package_dir}") from exc


def _import_package_with_unique_name(package_dir: Path) -> ModuleType:
    init_file = package_dir / "__init__.py"
    package_hash = hashlib.sha256(str(init_file.resolve()).encode()).hexdigest()[:16]
    unique_module_name = f"_zorix_plugin_{package_hash}"

    spec = importlib.util.spec_from_file_location(
        unique_module_name,
        init_file,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import adapter package from {package_dir}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        _clear_module_cache(unique_module_name)
        raise ImportError(f"Cannot import adapter package from {package_dir}") from exc

    return module


def _exported_adapter_classes(module: ModuleType) -> list[type[Adapter]]:
    adapter_classes: list[type[Adapter]] = []

    for export_name in ("Adapter", "MockAdapter"):
        if not hasattr(module, export_name):
            continue

        candidate = getattr(module, export_name)
        if not inspect.isclass(candidate):
            raise TypeError(f"{module.__name__}.{export_name} is not a class")

        if not issubclass(candidate, Adapter):
            raise TypeError(f"{module.__name__}.{export_name} is not an Adapter")

        adapter_classes.append(candidate)

    return adapter_classes


def _python_paths_for(root: Path) -> list[Path]:
    paths: list[Path] = [root, root.parent]

    for base in (root, root.parent):
        src_dir = base / "src"
        if src_dir.is_dir():
            paths.append(src_dir)

        if not base.is_dir():
            continue

        for child in sorted(base.iterdir()):
            child_src_dir = child / "src"
            if child.is_dir() and child_src_dir.is_dir():
                paths.append(child_src_dir)

    return _unique_paths(paths)


@contextmanager
def _temporary_python_paths(paths: list[Path]) -> Iterator[None]:
    original_path = list(sys.path)
    for path in reversed(paths):
        path_value = str(path)
        if path_value not in sys.path:
            sys.path.insert(0, path_value)

    try:
        yield
    finally:
        sys.path[:] = original_path


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()

    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)

    return unique


def _clear_module_cache(module_name: str) -> None:
    for cached_name in list(sys.modules):
        if cached_name == module_name or cached_name.startswith(f"{module_name}."):
            del sys.modules[cached_name]
