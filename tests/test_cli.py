from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from zorix.cli import main
from zorix_core_model import Resource
from zorix_scan_engine import ScanResult, ScanStatus


def _resource(resource_id: str, resource_type: str, name: str) -> Resource:
    return Resource(
        id=resource_id,
        type=resource_type,
        name=name,
        state="active",
    )


def _result(status: ScanStatus) -> ScanResult:
    resources = ()
    errors = ()
    if status is not ScanStatus.FAILED:
        resources = (_resource("service-1", "service", "api"),)

    return ScanResult(status=status, resources=resources, errors=errors)


class FakeRuntime:
    def __init__(
        self,
        result: ScanResult | None = None,
        *,
        error_on_load: Exception | None = None,
        error_on_scan: Exception | None = None,
        call_order: list[str] | None = None,
    ) -> None:
        self.result = result or _result(ScanStatus.SUCCESS)
        self.error_on_load = error_on_load
        self.error_on_scan = error_on_scan
        self.call_order = call_order if call_order is not None else []
        self.loaded_paths: list[Path] = []
        self.continue_on_error_values: list[bool] = []
        self._adapters = (object(),)

    def load_plugins(self, path: Path) -> tuple[object, ...]:
        self.call_order.append("load_plugins")
        self.loaded_paths.append(path)
        if self.error_on_load is not None:
            raise self.error_on_load
        return self._adapters

    def scan(self, *, continue_on_error: bool = False) -> ScanResult:
        self.call_order.append("scan")
        self.continue_on_error_values.append(continue_on_error)
        if self.error_on_scan is not None:
            raise self.error_on_scan
        return self.result

    def adapters(self) -> tuple[object, ...]:
        self.call_order.append("adapters")
        return self._adapters


class FakeRenderer:
    def __init__(self, call_order: list[str] | None = None, text: str = "rendered output\n") -> None:
        self.call_order = call_order if call_order is not None else []
        self.text = text
        self.received_result: ScanResult | None = None
        self.received_adapter_count: int | None = None

    def render(self, result: ScanResult, *, adapter_count: int | None = None) -> str:
        self.call_order.append("render")
        self.received_result = result
        self.received_adapter_count = adapter_count
        return self.text


class EmptyMessageError(Exception):
    def __str__(self) -> str:
        return ""


class CliTest(unittest.TestCase):
    def test_version_outputs_version(self) -> None:
        code, stdout, stderr = _run_main(["--version"])

        self.assertEqual(stdout, "zorix 0.1.0\n")
        self.assertEqual(stderr, "")
        self.assertEqual(code, 0)

    def test_version_returns_zero(self) -> None:
        code, _, _ = _run_main(["--version"])

        self.assertEqual(code, 0)

    def test_python_api_version_does_not_raise_system_exit(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["--version"])

        self.assertEqual(code, 0)

    def test_scan_delegates_load_plugins_to_runtime(self) -> None:
        runtime = FakeRuntime()
        code, _, _ = _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 0)
        self.assertEqual(len(runtime.loaded_paths), 1)

    def test_scan_passes_plugin_path_as_path(self) -> None:
        runtime = FakeRuntime()

        _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertIsInstance(runtime.loaded_paths[0], Path)
        self.assertEqual(runtime.loaded_paths[0], Path("plugins"))

    def test_scan_calls_runtime_scan(self) -> None:
        runtime = FakeRuntime()

        _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(runtime.continue_on_error_values, [False])

    def test_continue_on_error_defaults_to_false(self) -> None:
        runtime = FakeRuntime()

        _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(runtime.continue_on_error_values, [False])

    def test_continue_on_error_flag_passes_true(self) -> None:
        runtime = FakeRuntime()

        _run_main(["scan", "--plugins", "plugins", "--continue-on-error"], runtime=runtime)

        self.assertEqual(runtime.continue_on_error_values, [True])

    def test_renderer_receives_scan_result(self) -> None:
        result = _result(ScanStatus.SUCCESS)
        runtime = FakeRuntime(result)
        renderer = FakeRenderer()

        _run_main(["scan", "--plugins", "plugins"], runtime=runtime, renderer=renderer)

        self.assertIs(renderer.received_result, result)

    def test_renderer_receives_adapter_count(self) -> None:
        renderer = FakeRenderer()

        _run_main(["scan", "--plugins", "plugins"], renderer=renderer)

        self.assertEqual(renderer.received_adapter_count, 1)

    def test_renderer_output_goes_to_stdout(self) -> None:
        renderer = FakeRenderer(text="hello\n")

        _, stdout, stderr = _run_main(["scan", "--plugins", "plugins"], renderer=renderer)

        self.assertEqual(stdout, "hello\n")
        self.assertEqual(stderr, "")

    def test_stderr_empty_on_success(self) -> None:
        _, _, stderr = _run_main(["scan", "--plugins", "plugins"])

        self.assertEqual(stderr, "")

    def test_success_returns_zero(self) -> None:
        code, _, _ = _run_main(["scan", "--plugins", "plugins"], runtime=FakeRuntime(_result(ScanStatus.SUCCESS)))

        self.assertEqual(code, 0)

    def test_partial_returns_three(self) -> None:
        code, _, _ = _run_main(["scan", "--plugins", "plugins"], runtime=FakeRuntime(_result(ScanStatus.PARTIAL)))

        self.assertEqual(code, 3)

    def test_failed_returns_four(self) -> None:
        code, _, _ = _run_main(["scan", "--plugins", "plugins"], runtime=FakeRuntime(_result(ScanStatus.FAILED)))

        self.assertEqual(code, 4)

    def test_load_plugins_error_returns_one(self) -> None:
        runtime = FakeRuntime(error_on_load=RuntimeError("load failed"))

        code, stdout, stderr = _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Error: RuntimeError: load failed\n", stderr)

    def test_scan_error_returns_one(self) -> None:
        runtime = FakeRuntime(error_on_scan=RuntimeError("scan failed"))

        code, stdout, stderr = _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Error: RuntimeError: scan failed\n", stderr)

    def test_execution_error_goes_to_stderr(self) -> None:
        runtime = FakeRuntime(error_on_load=ValueError("bad plugin"))

        _, stdout, stderr = _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: ValueError: bad plugin\n")

    def test_execution_error_does_not_show_traceback(self) -> None:
        runtime = FakeRuntime(error_on_load=RuntimeError("load failed"))

        _, _, stderr = _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertNotIn("Traceback", stderr)

    def test_empty_error_message_has_no_extra_colon(self) -> None:
        runtime = FakeRuntime(error_on_load=EmptyMessageError())

        _, _, stderr = _run_main(["scan", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(stderr, "Error: EmptyMessageError\n")

    def test_unknown_command_uses_argparse_code_two(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as context:
            main(["unknown"])

        self.assertEqual(context.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())

    def test_missing_plugins_uses_argparse_code_two(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as context:
            main(["scan"])

        self.assertEqual(context.exception.code, 2)
        self.assertIn("--plugins", stderr.getvalue())

    def test_main_module_exists(self) -> None:
        spec = importlib.util.find_spec("zorix.__main__")

        self.assertIsNotNone(spec)

    def test_cli_uses_console_renderer_factory(self) -> None:
        renderer = FakeRenderer(text="from renderer\n")

        _, stdout, _ = _run_main(["scan", "--plugins", "plugins"], renderer=renderer)

        self.assertEqual(stdout, "from renderer\n")
        self.assertIsNotNone(renderer.received_result)

    def test_scan_call_order(self) -> None:
        call_order: list[str] = []
        runtime = FakeRuntime(call_order=call_order)
        renderer = FakeRenderer(call_order=call_order)

        _run_main(["scan", "--plugins", "plugins"], runtime=runtime, renderer=renderer)

        self.assertEqual(call_order, ["load_plugins", "scan", "adapters", "render"])

    def test_integration_scan_with_real_runtime_and_temp_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "test_cli_adapter"
            plugin_dir.mkdir()
            (plugin_dir / "__init__.py").write_text(
                textwrap.dedent(
                    """
                    from zorix_core_model import Adapter as BaseAdapter, Resource


                    class Adapter(BaseAdapter):
                        def discover(self):
                            return [
                                Resource(
                                    id="cli-service-1",
                                    type="service",
                                    name="cli-api",
                                    state="active",
                                )
                            ]
                    """
                ).strip(),
                encoding="utf-8",
            )

            code, stdout, stderr = _run_main_without_patches(["scan", "--plugins", directory])

        self.assertEqual(code, 0)
        self.assertIn("Status: SUCCESS\n", stdout)
        self.assertIn("Adapters: 1\n", stdout)
        self.assertIn("- Service: cli-api\n", stdout)
        self.assertEqual(stderr, "")


def _run_main(
    argv: list[str],
    *,
    runtime: FakeRuntime | None = None,
    renderer: FakeRenderer | None = None,
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    runtime = runtime if runtime is not None else FakeRuntime()
    renderer = renderer if renderer is not None else FakeRenderer()

    with patch("zorix.cli._create_runtime", return_value=runtime):
        with patch("zorix.cli._create_renderer", return_value=renderer):
            with redirect_stdout(stdout):
                with redirect_stderr(stderr):
                    code = main(argv)

    return code, stdout.getvalue(), stderr.getvalue()


def _run_main_without_patches(argv: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()

    with redirect_stdout(stdout):
        with redirect_stderr(stderr):
            code = main(argv)

    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
