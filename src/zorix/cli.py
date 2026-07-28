from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from zorix_presentation import ConsoleRenderer
from zorix_runtime import ZorixRuntime
from zorix_scan_engine import ScanStatus

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


def _create_runtime() -> ZorixRuntime:
    return ZorixRuntime()


def _create_renderer() -> ConsoleRenderer:
    return ConsoleRenderer()


def _exit_code(status: ScanStatus) -> int:
    if status is ScanStatus.SUCCESS:
        return 0

    if status is ScanStatus.PARTIAL:
        return 3

    if status is ScanStatus.FAILED:
        return 4

    return 1


def _format_execution_error(error: Exception) -> str:
    message = str(error).strip()
    if message:
        return f"Error: {type(error).__name__}: {message}"

    return f"Error: {type(error).__name__}"
