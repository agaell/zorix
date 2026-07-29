from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from zorix_health_engine import HealthStatus
from zorix_health_model import HealthLevel
from zorix_presentation import ConsoleRenderer, HealthConsoleRenderer, TopologyConsoleRenderer
from zorix_runtime import ZorixRuntime
from zorix_scan_engine import ScanStatus
from zorix_topology_engine import TopologyStatus

from . import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"zorix {__version__}")
        return 0

    if args.command == "scan":
        try:
            return _run_scan(args)
        except Exception as error:
            print(_format_execution_error(error), file=sys.stderr)
            return 1

    if args.command == "topology":
        try:
            return _run_topology(args)
        except Exception as error:
            print(_format_execution_error(error), file=sys.stderr)
            return 1

    if args.command == "health":
        try:
            return _run_health(args)
        except Exception as error:
            print(_format_execution_error(error), file=sys.stderr)
            return 1

    parser.error("a command is required")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zorix",
        description="Zorix command-line interface.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="show Zorix version and exit",
    )

    subparsers = parser.add_subparsers(dest="command")
    scan_parser = subparsers.add_parser(
        "scan",
        help="discover resources through loaded adapters",
        description="Discover resources through adapters loaded from a plugin directory.",
    )
    scan_parser.add_argument(
        "--plugins",
        type=Path,
        required=True,
        help="path to a directory with adapter plugins",
    )
    scan_parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="continue scanning remaining adapters after adapter errors",
    )

    topology_parser = subparsers.add_parser(
        "topology",
        help="discover resources and build topology",
        description="Discover resources and build their topology.",
    )
    topology_parser.add_argument(
        "--plugins",
        type=Path,
        required=True,
        help="path to a directory with adapter plugins",
    )
    topology_parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="continue scanning and topology building after adapter/provider errors",
    )

    health_parser = subparsers.add_parser(
        "health",
        help="discover resources and evaluate health",
        description="Discover resources and evaluate their health.",
    )
    health_parser.add_argument(
        "--plugins",
        type=Path,
        required=True,
        help="path to a directory with adapter plugins",
    )
    health_parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="continue scanning and health evaluation after adapter/provider errors",
    )

    return parser


def _run_scan(args: argparse.Namespace) -> int:
    runtime = _create_runtime()
    renderer = _create_renderer()

    runtime.load_plugins(args.plugins)
    result = runtime.scan(continue_on_error=args.continue_on_error)
    adapter_count = len(runtime.adapters())
    text = renderer.render(result, adapter_count=adapter_count)
    print(text, end="")

    return _exit_code(result.status)


def _run_topology(args: argparse.Namespace) -> int:
    runtime = _create_runtime()
    scan_renderer = _create_renderer()
    topology_renderer = _create_topology_renderer()

    runtime.load_plugins(args.plugins)
    scan_result = runtime.scan(continue_on_error=args.continue_on_error)
    adapter_count = len(runtime.adapters())
    scan_text = scan_renderer.render(scan_result, adapter_count=adapter_count)

    if scan_result.status is ScanStatus.FAILED:
        print(scan_text, end="")
        return 4

    topology_result = runtime.build_topology(
        scan_result.resources,
        continue_on_error=args.continue_on_error,
    )
    topology_text = topology_renderer.render(topology_result)
    text = _join_rendered_sections(scan_text, topology_text)
    print(text, end="")

    return _topology_workflow_exit_code(scan_result.status, topology_result.status)


def _run_health(args: argparse.Namespace) -> int:
    runtime = _create_runtime()
    scan_renderer = _create_renderer()
    health_renderer = _create_health_renderer()

    runtime.load_plugins(args.plugins)
    scan_result = runtime.scan(continue_on_error=args.continue_on_error)

    if scan_result.status is ScanStatus.FAILED:
        adapter_count = len(runtime.adapters())
        scan_text = scan_renderer.render(scan_result, adapter_count=adapter_count)
        print(scan_text, end="")
        return 4

    health_result = runtime.evaluate_health(
        scan_result.resources,
        continue_on_error=args.continue_on_error,
    )
    health_text = health_renderer.render(health_result)

    if scan_result.status is ScanStatus.PARTIAL:
        adapter_count = len(runtime.adapters())
        scan_text = scan_renderer.render(scan_result, adapter_count=adapter_count)
        text = _join_rendered_sections(scan_text, health_text)
    else:
        text = health_text

    print(text, end="")
    return _health_workflow_exit_code(scan_result.status, health_result.status, health_result.level)


def _create_runtime() -> ZorixRuntime:
    return ZorixRuntime()


def _create_renderer() -> ConsoleRenderer:
    return ConsoleRenderer()


def _create_topology_renderer() -> TopologyConsoleRenderer:
    return TopologyConsoleRenderer()


def _create_health_renderer() -> HealthConsoleRenderer:
    return HealthConsoleRenderer()


def _exit_code(status: ScanStatus) -> int:
    if status is ScanStatus.SUCCESS:
        return 0

    if status is ScanStatus.PARTIAL:
        return 3

    if status is ScanStatus.FAILED:
        return 4

    return 1


def _topology_workflow_exit_code(
    scan_status: ScanStatus,
    topology_status: TopologyStatus,
) -> int:
    if scan_status is ScanStatus.FAILED or topology_status is TopologyStatus.FAILED:
        return 4

    if scan_status is ScanStatus.PARTIAL or topology_status is TopologyStatus.PARTIAL:
        return 3

    if scan_status is ScanStatus.SUCCESS and topology_status is TopologyStatus.SUCCESS:
        return 0

    return 1


def _health_workflow_exit_code(
    scan_status: ScanStatus,
    health_status: HealthStatus,
    health_level: HealthLevel,
) -> int:
    if scan_status is ScanStatus.FAILED:
        return 4
    if health_status is HealthStatus.FAILED:
        return 4
    if health_level is HealthLevel.CRITICAL:
        return 4
    if scan_status is ScanStatus.PARTIAL:
        return 3
    if health_status is HealthStatus.PARTIAL:
        return 3
    if health_level is HealthLevel.WARNING:
        return 3
    return 0


def _join_rendered_sections(first: str, second: str) -> str:
    return first.rstrip("\n") + "\n\n" + second.lstrip("\n").rstrip("\n") + "\n"


def _format_execution_error(error: Exception) -> str:
    message = str(error).strip()
    if message:
        return f"Error: {type(error).__name__}: {message}"

    return f"Error: {type(error).__name__}"
