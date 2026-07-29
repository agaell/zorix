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
from zorix_action_model import (
    ActionPlan,
    ActionPlanResult,
    ActionPlanStatus,
    ActionRejection,
    ActionRequest,
    ActionRisk,
    ActionStep,
)
from zorix_core_model import Resource
from zorix_health_engine import HealthProviderError, HealthResult, HealthStatus
from zorix_health_model import HealthFinding, HealthLevel, HealthSeverity
from zorix_resource_graph import ResourceGraphBuilder, ResourceRelation
from zorix_scan_engine import ScanResult, ScanStatus
from zorix_topology_engine import TopologyProviderError, TopologyResult, TopologyStatus


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


def _topology_result(status: TopologyStatus) -> TopologyResult:
    builder = ResourceGraphBuilder()
    builder.add_resources(
        (
            _resource("service:api", "service", "api"),
            _resource("database:main", "database", "main"),
        )
    )
    if status is not TopologyStatus.FAILED:
        builder.add_relation(ResourceRelation("service:api", "database:main", "depends_on"))

    errors = ()
    provider_count = 1
    successful_provider_count = 1
    if status is TopologyStatus.PARTIAL:
        provider_count = 2
        successful_provider_count = 1
        errors = (TopologyProviderError("example.Broken", "RuntimeError", "broken"),)
    elif status is TopologyStatus.FAILED:
        successful_provider_count = 0
        errors = (TopologyProviderError("example.Broken", "RuntimeError", "broken"),)

    return TopologyResult(
        status=status,
        graph=builder.build(),
        errors=errors,
        provider_count=provider_count,
        successful_provider_count=successful_provider_count,
    )


def _health_result(
    status: HealthStatus = HealthStatus.SUCCESS,
    level: HealthLevel = HealthLevel.HEALTHY,
) -> HealthResult:
    findings = ()
    errors = ()
    provider_count = 1
    successful_provider_count = 1
    if level is HealthLevel.WARNING:
        findings = (
            HealthFinding("test", "test.warning", HealthSeverity.WARNING, "service-1", "warning"),
        )
    elif level is HealthLevel.CRITICAL:
        findings = (
            HealthFinding("test", "test.critical", HealthSeverity.CRITICAL, "service-1", "critical"),
        )

    if status is HealthStatus.PARTIAL:
        provider_count = 2
        errors = (HealthProviderError("example.Broken", "RuntimeError", "broken"),)
    elif status is HealthStatus.FAILED:
        successful_provider_count = 0
        errors = (HealthProviderError("example.Broken", "RuntimeError", "broken"),)

    return HealthResult(
        status=status,
        level=level,
        findings=findings,
        errors=errors,
        provider_count=provider_count,
        successful_provider_count=successful_provider_count,
        resource_count=1,
    )


def _action_result(status: ActionPlanStatus = ActionPlanStatus.READY) -> ActionPlanResult:
    request = ActionRequest("service.restart", "service-1")
    if status is ActionPlanStatus.REJECTED:
        return ActionPlanResult(
            status=ActionPlanStatus.REJECTED,
            request=request,
            rejection=ActionRejection("action.unsupported", "unsupported"),
            provider_count=1,
        )

    return ActionPlanResult(
        status=ActionPlanStatus.READY,
        request=request,
        plan=ActionPlan(
            source="test",
            provider="provider.Class",
            request=request,
            resource_name="api",
            operation="test.operation",
            risk=ActionRisk.MEDIUM,
            requires_confirmation=True,
            summary="Plan action",
            steps=(ActionStep(1, "step.one", "First step"),),
        ),
        provider_count=1,
    )


class FakeRuntime:
    def __init__(
        self,
        result: ScanResult | None = None,
        *,
        error_on_load: Exception | None = None,
        error_on_scan: Exception | None = None,
        error_on_topology: Exception | None = None,
        error_on_health: Exception | None = None,
        error_on_action: Exception | None = None,
        call_order: list[str] | None = None,
        topology_result: TopologyResult | None = None,
        health_result: HealthResult | None = None,
        action_result: ActionPlanResult | None = None,
    ) -> None:
        self.result = result or _result(ScanStatus.SUCCESS)
        self.topology_result = topology_result or _topology_result(TopologyStatus.SUCCESS)
        self.health_result = health_result or _health_result()
        self.action_result = action_result or _action_result()
        self.error_on_load = error_on_load
        self.error_on_scan = error_on_scan
        self.error_on_topology = error_on_topology
        self.error_on_health = error_on_health
        self.error_on_action = error_on_action
        self.call_order = call_order if call_order is not None else []
        self.loaded_paths: list[Path] = []
        self.continue_on_error_values: list[bool] = []
        self.topology_continue_on_error_values: list[bool] = []
        self.health_continue_on_error_values: list[bool] = []
        self.topology_resources: object | None = None
        self.health_resources: object | None = None
        self.action_resources: object | None = None
        self.action_request: ActionRequest | None = None
        self.build_topology_called = False
        self.evaluate_health_called = False
        self.plan_action_called = False
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

    def build_topology(
        self,
        resources: object,
        *,
        continue_on_error: bool = False,
    ) -> TopologyResult:
        self.call_order.append("build_topology")
        self.build_topology_called = True
        self.topology_resources = resources
        self.topology_continue_on_error_values.append(continue_on_error)
        if self.error_on_topology is not None:
            raise self.error_on_topology
        return self.topology_result

    def evaluate_health(
        self,
        resources: object,
        *,
        continue_on_error: bool = False,
    ) -> HealthResult:
        self.call_order.append("evaluate_health")
        self.evaluate_health_called = True
        self.health_resources = resources
        self.health_continue_on_error_values.append(continue_on_error)
        if self.error_on_health is not None:
            raise self.error_on_health
        return self.health_result

    def plan_action(
        self,
        resources: object,
        request: ActionRequest,
    ) -> ActionPlanResult:
        self.call_order.append("plan_action")
        self.plan_action_called = True
        self.action_resources = resources
        self.action_request = request
        if self.error_on_action is not None:
            raise self.error_on_action
        return self.action_result

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


class FakeTopologyRenderer:
    def __init__(
        self,
        call_order: list[str] | None = None,
        text: str = "topology output\n",
        error: Exception | None = None,
    ) -> None:
        self.call_order = call_order if call_order is not None else []
        self.text = text
        self.error = error
        self.received_result: TopologyResult | None = None

    def render(self, result: TopologyResult) -> str:
        self.call_order.append("topology_render")
        self.received_result = result
        if self.error is not None:
            raise self.error
        return self.text


class FakeHealthRenderer:
    def __init__(
        self,
        call_order: list[str] | None = None,
        text: str = "health output\n",
        error: Exception | None = None,
    ) -> None:
        self.call_order = call_order if call_order is not None else []
        self.text = text
        self.error = error
        self.received_result: HealthResult | None = None

    def render(self, result: HealthResult) -> str:
        self.call_order.append("health_render")
        self.received_result = result
        if self.error is not None:
            raise self.error
        return self.text


class FakeActionPlanRenderer:
    def __init__(
        self,
        call_order: list[str] | None = None,
        text: str = "action output\n",
        error: Exception | None = None,
    ) -> None:
        self.call_order = call_order if call_order is not None else []
        self.text = text
        self.error = error
        self.received_result: ActionPlanResult | None = None

    def render(self, result: ActionPlanResult) -> str:
        self.call_order.append("action_render")
        self.received_result = result
        if self.error is not None:
            raise self.error
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

    def test_topology_command_requires_plugins(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as context:
            main(["topology"])

        self.assertEqual(context.exception.code, 2)
        self.assertIn("--plugins", stderr.getvalue())

    def test_topology_unknown_argument_uses_argparse_code_two(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as context:
            main(["topology", "--plugins", "plugins", "--json"])

        self.assertEqual(context.exception.code, 2)
        self.assertIn("unrecognized arguments", stderr.getvalue())

    def test_topology_help_uses_argparse_code_zero(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout), self.assertRaises(SystemExit) as context:
            main(["topology", "--help"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("Discover resources and build their topology.", stdout.getvalue())
        self.assertIn("--plugins", stdout.getvalue())
        self.assertIn("--continue-on-error", stdout.getvalue())

    def test_topology_passes_plugin_path_as_path(self) -> None:
        runtime = FakeRuntime()

        _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(runtime.loaded_paths, [Path("plugins")])

    def test_topology_continue_on_error_defaults_to_false(self) -> None:
        runtime = FakeRuntime()

        _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(runtime.continue_on_error_values, [False])
        self.assertEqual(runtime.topology_continue_on_error_values, [False])

    def test_topology_continue_on_error_flag_passes_true_to_both_phases(self) -> None:
        runtime = FakeRuntime()

        _run_main(["topology", "--plugins", "plugins", "--continue-on-error"], runtime=runtime)

        self.assertEqual(runtime.continue_on_error_values, [True])
        self.assertEqual(runtime.topology_continue_on_error_values, [True])

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

    def test_topology_call_order_and_renderers(self) -> None:
        call_order: list[str] = []
        runtime = FakeRuntime(call_order=call_order)
        scan_renderer = FakeRenderer(call_order=call_order, text="scan output\n")
        topology_renderer = FakeTopologyRenderer(call_order=call_order, text="topology output\n")

        code, stdout, stderr = _run_main(
            ["topology", "--plugins", "plugins"],
            runtime=runtime,
            renderer=scan_renderer,
            topology_renderer=topology_renderer,
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            call_order,
            [
                "load_plugins",
                "scan",
                "adapters",
                "render",
                "build_topology",
                "topology_render",
            ],
        )
        self.assertIs(runtime.topology_resources, runtime.result.resources)
        self.assertEqual(scan_renderer.received_adapter_count, 1)
        self.assertIs(topology_renderer.received_result, runtime.topology_result)
        self.assertEqual(stdout, "scan output\n\ntopology output\n")
        self.assertEqual(stderr, "")

    def test_topology_joined_output_has_single_blank_line_and_one_final_newline(self) -> None:
        scan_renderer = FakeRenderer(text="scan output\n\n")
        topology_renderer = FakeTopologyRenderer(text="\ntopology output\n\n")

        _, stdout, stderr = _run_main(
            ["topology", "--plugins", "plugins"],
            renderer=scan_renderer,
            topology_renderer=topology_renderer,
        )

        self.assertEqual(stdout, "scan output\n\ntopology output\n")
        self.assertFalse(stdout.endswith("\n\n"))
        self.assertNotIn("\n\n\n", stdout)
        self.assertEqual(stderr, "")

    def test_topology_success_success_returns_zero(self) -> None:
        runtime = FakeRuntime(
            _result(ScanStatus.SUCCESS),
            topology_result=_topology_result(TopologyStatus.SUCCESS),
        )

        code, _, _ = _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 0)

    def test_topology_partial_scan_success_topology_returns_three(self) -> None:
        runtime = FakeRuntime(
            _result(ScanStatus.PARTIAL),
            topology_result=_topology_result(TopologyStatus.SUCCESS),
        )

        code, _, _ = _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 3)

    def test_topology_success_scan_partial_topology_returns_three(self) -> None:
        runtime = FakeRuntime(
            _result(ScanStatus.SUCCESS),
            topology_result=_topology_result(TopologyStatus.PARTIAL),
        )

        code, _, _ = _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 3)

    def test_topology_partial_partial_returns_three(self) -> None:
        runtime = FakeRuntime(
            _result(ScanStatus.PARTIAL),
            topology_result=_topology_result(TopologyStatus.PARTIAL),
        )

        code, _, _ = _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 3)

    def test_topology_success_scan_failed_topology_returns_four(self) -> None:
        runtime = FakeRuntime(
            _result(ScanStatus.SUCCESS),
            topology_result=_topology_result(TopologyStatus.FAILED),
        )

        code, stdout, stderr = _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 4)
        self.assertIn("topology output\n", stdout)
        self.assertEqual(stderr, "")

    def test_topology_partial_scan_failed_topology_returns_four(self) -> None:
        runtime = FakeRuntime(
            _result(ScanStatus.PARTIAL),
            topology_result=_topology_result(TopologyStatus.FAILED),
        )

        code, _, _ = _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 4)

    def test_scan_failed_prints_only_scan_result_and_does_not_build_topology(self) -> None:
        runtime = FakeRuntime(_result(ScanStatus.FAILED))
        scan_renderer = FakeRenderer(text="failed scan\n")
        topology_renderer = FakeTopologyRenderer(text="topology output\n")

        code, stdout, stderr = _run_main(
            ["topology", "--plugins", "plugins"],
            runtime=runtime,
            renderer=scan_renderer,
            topology_renderer=topology_renderer,
        )

        self.assertEqual(code, 4)
        self.assertEqual(stdout, "failed scan\n")
        self.assertEqual(stderr, "")
        self.assertFalse(runtime.build_topology_called)
        self.assertIsNone(topology_renderer.received_result)

    def test_topology_load_plugins_error_returns_one(self) -> None:
        runtime = FakeRuntime(error_on_load=RuntimeError("load failed"))

        code, stdout, stderr = _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: RuntimeError: load failed\n")

    def test_topology_scan_error_returns_one(self) -> None:
        runtime = FakeRuntime(error_on_scan=RuntimeError("scan failed"))

        code, stdout, stderr = _run_main(["topology", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: RuntimeError: scan failed\n")

    def test_topology_build_error_returns_one_without_partial_stdout(self) -> None:
        runtime = FakeRuntime(error_on_topology=RuntimeError("topology failed"))
        scan_renderer = FakeRenderer(text="scan text\n")

        code, stdout, stderr = _run_main(
            ["topology", "--plugins", "plugins"],
            runtime=runtime,
            renderer=scan_renderer,
        )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: RuntimeError: topology failed\n")
        self.assertNotIn("scan text", stdout)
        self.assertNotIn("Traceback", stderr)

    def test_topology_renderer_error_returns_one_without_stdout(self) -> None:
        topology_renderer = FakeTopologyRenderer(error=RuntimeError("render failed"))

        code, stdout, stderr = _run_main(
            ["topology", "--plugins", "plugins"],
            topology_renderer=topology_renderer,
        )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: RuntimeError: render failed\n")

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

    def test_integration_topology_with_real_runtime_and_temp_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "test_cli_topology_adapter"
            plugin_dir.mkdir()
            counter_file = Path(directory) / "discover-count.txt"
            (plugin_dir / "__init__.py").write_text(
                textwrap.dedent(
                    f"""
                    from pathlib import Path

                    from zorix_core_model import Adapter as BaseAdapter, Resource
                    from zorix_resource_graph import ResourceRelation

                    COUNTER_FILE = Path({str(counter_file)!r})


                    class Adapter(BaseAdapter):
                        def discover(self):
                            count = 0
                            if COUNTER_FILE.exists():
                                count = int(COUNTER_FILE.read_text(encoding="utf-8"))
                            COUNTER_FILE.write_text(str(count + 1), encoding="utf-8")
                            return [
                                Resource("service:api", "service", "api", "active"),
                                Resource("database:main", "database", "main", "active"),
                            ]

                        def discover_relations(self, context):
                            return [
                                ResourceRelation(
                                    "service:api",
                                    "database:main",
                                    "depends_on",
                                )
                            ]
                    """
                ).strip(),
                encoding="utf-8",
            )

            code, stdout, stderr = _run_main_without_patches(["topology", "--plugins", directory])
            discover_count = counter_file.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Status: SUCCESS\n", stdout)
        self.assertIn("Adapters: 1\n", stdout)
        self.assertIn("Resources: 2\n", stdout)
        self.assertIn("- Service: api\n", stdout)
        self.assertIn("- Database: main\n", stdout)
        self.assertIn("Topology: SUCCESS\n", stdout)
        self.assertIn("Providers: 1\n", stdout)
        self.assertIn("Successful providers: 1\n", stdout)
        self.assertIn("Failed providers: 0\n", stdout)
        self.assertIn("Relations: 1\n", stdout)
        self.assertIn("- Service api --depends_on--> Database main\n", stdout)
        self.assertEqual(discover_count, "1")

    def test_health_command_requires_plugins(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as context:
            main(["health"])

        self.assertEqual(context.exception.code, 2)
        self.assertIn("--plugins", stderr.getvalue())

    def test_health_help_uses_argparse_code_zero(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout), self.assertRaises(SystemExit) as context:
            main(["health", "--help"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("Discover resources and evaluate their health.", stdout.getvalue())
        self.assertIn("--plugins", stdout.getvalue())
        self.assertIn("--continue-on-error", stdout.getvalue())

    def test_health_passes_plugin_path_as_path(self) -> None:
        runtime = FakeRuntime()

        _run_main(["health", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(runtime.loaded_paths, [Path("plugins")])

    def test_health_continue_on_error_flag_passes_true_to_scan_and_health(self) -> None:
        runtime = FakeRuntime()

        _run_main(["health", "--plugins", "plugins", "--continue-on-error"], runtime=runtime)

        self.assertEqual(runtime.continue_on_error_values, [True])
        self.assertEqual(runtime.health_continue_on_error_values, [True])

    def test_health_workflow_order_scan_success(self) -> None:
        call_order: list[str] = []
        runtime = FakeRuntime(call_order=call_order)
        scan_renderer = FakeRenderer(call_order=call_order, text="scan output\n")
        health_renderer = FakeHealthRenderer(call_order=call_order, text="health output\n")

        code, stdout, stderr = _run_main(
            ["health", "--plugins", "plugins"],
            runtime=runtime,
            renderer=scan_renderer,
            health_renderer=health_renderer,
        )

        self.assertEqual(code, 0)
        self.assertEqual(call_order, ["load_plugins", "scan", "evaluate_health", "health_render"])
        self.assertEqual(stdout, "health output\n")
        self.assertEqual(stderr, "")
        self.assertIs(runtime.health_resources, runtime.result.resources)
        self.assertIs(health_renderer.received_result, runtime.health_result)

    def test_health_scan_partial_prints_scan_and_health(self) -> None:
        runtime = FakeRuntime(_result(ScanStatus.PARTIAL))
        scan_renderer = FakeRenderer(text="scan output\n")
        health_renderer = FakeHealthRenderer(text="health output\n")

        code, stdout, stderr = _run_main(
            ["health", "--plugins", "plugins"],
            runtime=runtime,
            renderer=scan_renderer,
            health_renderer=health_renderer,
        )

        self.assertEqual(code, 3)
        self.assertEqual(stdout, "scan output\n\nhealth output\n")
        self.assertEqual(stderr, "")

    def test_health_scan_failed_prints_only_scan_result_and_does_not_evaluate_health(self) -> None:
        runtime = FakeRuntime(_result(ScanStatus.FAILED))
        scan_renderer = FakeRenderer(text="failed scan\n")
        health_renderer = FakeHealthRenderer(text="health output\n")

        code, stdout, stderr = _run_main(
            ["health", "--plugins", "plugins"],
            runtime=runtime,
            renderer=scan_renderer,
            health_renderer=health_renderer,
        )

        self.assertEqual(code, 4)
        self.assertEqual(stdout, "failed scan\n")
        self.assertEqual(stderr, "")
        self.assertFalse(runtime.evaluate_health_called)
        self.assertIsNone(health_renderer.received_result)

    def test_health_exit_codes(self) -> None:
        cases = (
            (_health_result(HealthStatus.SUCCESS, HealthLevel.HEALTHY), 0),
            (_health_result(HealthStatus.SUCCESS, HealthLevel.WARNING), 3),
            (_health_result(HealthStatus.SUCCESS, HealthLevel.CRITICAL), 4),
            (_health_result(HealthStatus.PARTIAL, HealthLevel.HEALTHY), 3),
            (_health_result(HealthStatus.FAILED, HealthLevel.HEALTHY), 4),
        )

        for health_result, expected_code in cases:
            with self.subTest(health_result=health_result):
                runtime = FakeRuntime(health_result=health_result)
                code, _, _ = _run_main(["health", "--plugins", "plugins"], runtime=runtime)
                self.assertEqual(code, expected_code)

    def test_health_execution_exception_returns_one_without_stdout(self) -> None:
        runtime = FakeRuntime(error_on_health=RuntimeError("health failed"))

        code, stdout, stderr = _run_main(["health", "--plugins", "plugins"], runtime=runtime)

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: RuntimeError: health failed\n")

    def test_integration_health_with_real_runtime_and_temp_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "test_cli_health_adapter"
            plugin_dir.mkdir()
            (plugin_dir / "__init__.py").write_text(
                textwrap.dedent(
                    """
                    from zorix_core_model import Adapter as BaseAdapter, Resource
                    from zorix_health_model import HealthFinding, HealthSeverity


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

                        def evaluate_health(self, context):
                            return [
                                HealthFinding(
                                    "test",
                                    "test.info",
                                    HealthSeverity.INFO,
                                    "cli-service-1",
                                    "observed",
                                )
                            ]
                    """
                ).strip(),
                encoding="utf-8",
            )

            code, stdout, stderr = _run_main_without_patches(["health", "--plugins", directory])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Health evaluation: SUCCESS\n", stdout)
        self.assertIn("Health: HEALTHY\n", stdout)
        self.assertIn("Findings: 1\n", stdout)
        self.assertIn("- INFO test.info: observed [cli-service-1]\n", stdout)

    def test_action_plan_command_requires_arguments_and_plugins(self) -> None:
        cases = (
            ["action"],
            ["action", "plan"],
            ["action", "plan", "service.restart"],
            ["action", "plan", "service.restart", "service-1"],
        )

        for argv in cases:
            with self.subTest(argv=argv):
                stderr = StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as context:
                    main(argv)
                self.assertEqual(context.exception.code, 2)

    def test_action_plan_help(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout), self.assertRaises(SystemExit) as context:
            main(["action", "plan", "--help"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("Create a dry-run action plan.", stdout.getvalue())
        self.assertIn("--plugins", stdout.getvalue())
        self.assertIn("--continue-on-error", stdout.getvalue())

    def test_action_help(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout), self.assertRaises(SystemExit) as context:
            main(["action", "--help"])

        self.assertEqual(context.exception.code, 0)
        self.assertIn("Plan safe infrastructure actions.", stdout.getvalue())
        self.assertIn("plan", stdout.getvalue())

    def test_action_plan_path_continue_flag_and_request(self) -> None:
        runtime = FakeRuntime()

        _run_main(
            [
                "action",
                "plan",
                "service.restart",
                "service-1",
                "--plugins",
                "plugins",
                "--continue-on-error",
            ],
            runtime=runtime,
        )

        self.assertEqual(runtime.loaded_paths, [Path("plugins")])
        self.assertEqual(runtime.continue_on_error_values, [True])
        self.assertEqual(runtime.action_request, ActionRequest("service.restart", "service-1"))

    def test_action_plan_workflow_ready(self) -> None:
        call_order: list[str] = []
        runtime = FakeRuntime(call_order=call_order)
        scan_renderer = FakeRenderer(call_order=call_order, text="scan output\n")
        action_renderer = FakeActionPlanRenderer(call_order=call_order, text="action output\n")

        code, stdout, stderr = _run_main(
            ["action", "plan", "service.restart", "service-1", "--plugins", "plugins"],
            runtime=runtime,
            renderer=scan_renderer,
            action_renderer=action_renderer,
        )

        self.assertEqual(code, 0)
        self.assertEqual(call_order, ["load_plugins", "scan", "plan_action", "action_render"])
        self.assertEqual(stdout, "action output\n")
        self.assertEqual(stderr, "")
        self.assertIs(runtime.action_resources, runtime.result.resources)
        self.assertIs(action_renderer.received_result, runtime.action_result)

    def test_action_plan_scan_partial_prints_scan_and_action_and_returns_three(self) -> None:
        runtime = FakeRuntime(_result(ScanStatus.PARTIAL))

        code, stdout, stderr = _run_main(
            ["action", "plan", "service.restart", "service-1", "--plugins", "plugins"],
            runtime=runtime,
            renderer=FakeRenderer(text="scan output\n"),
            action_renderer=FakeActionPlanRenderer(text="action output\n"),
        )

        self.assertEqual(code, 3)
        self.assertEqual(stdout, "scan output\n\naction output\n")
        self.assertEqual(stderr, "")

    def test_action_plan_scan_failed_does_not_plan(self) -> None:
        runtime = FakeRuntime(_result(ScanStatus.FAILED))
        action_renderer = FakeActionPlanRenderer(text="action output\n")

        code, stdout, stderr = _run_main(
            ["action", "plan", "service.restart", "service-1", "--plugins", "plugins"],
            runtime=runtime,
            renderer=FakeRenderer(text="failed scan\n"),
            action_renderer=action_renderer,
        )

        self.assertEqual(code, 4)
        self.assertEqual(stdout, "failed scan\n")
        self.assertEqual(stderr, "")
        self.assertFalse(runtime.plan_action_called)
        self.assertIsNone(action_renderer.received_result)

    def test_action_plan_rejected_returns_four(self) -> None:
        runtime = FakeRuntime(action_result=_action_result(ActionPlanStatus.REJECTED))

        code, _, _ = _run_main(
            ["action", "plan", "service.restart", "service-1", "--plugins", "plugins"],
            runtime=runtime,
        )

        self.assertEqual(code, 4)

    def test_action_plan_exception_returns_one_without_stdout(self) -> None:
        runtime = FakeRuntime(error_on_action=RuntimeError("planning failed"))

        code, stdout, stderr = _run_main(
            ["action", "plan", "service.restart", "service-1", "--plugins", "plugins"],
            runtime=runtime,
        )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: RuntimeError: planning failed\n")

    def test_integration_action_plan_with_real_runtime_and_temp_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plugin_dir = Path(directory) / "test_cli_action_adapter"
            plugin_dir.mkdir()
            (plugin_dir / "__init__.py").write_text(
                textwrap.dedent(
                    """
                    from zorix_action_model import ActionPlan, ActionRisk, ActionStep
                    from zorix_core_model import Adapter as BaseAdapter, Resource


                    class Adapter(BaseAdapter):
                        def discover(self):
                            return [Resource("service-1", "service", "api", "active")]

                        def plan_action(self, context, request):
                            if request.action != "service.restart":
                                return None
                            return ActionPlan(
                                "test",
                                "test.Adapter",
                                request,
                                "api",
                                "test.restart",
                                ActionRisk.MEDIUM,
                                True,
                                "Restart api",
                                (ActionStep(1, "test.step", "Plan restart"),),
                            )
                    """
                ).strip(),
                encoding="utf-8",
            )

            code, stdout, stderr = _run_main_without_patches(
                [
                    "action",
                    "plan",
                    "service.restart",
                    "service-1",
                    "--plugins",
                    directory,
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Action planning: READY\n", stdout)
        self.assertIn("Dry run: yes\n", stdout)
        self.assertIn("Operation: test.restart\n", stdout)
        self.assertIn("Risk: MEDIUM\n", stdout)


def _run_main(
    argv: list[str],
    *,
    runtime: FakeRuntime | None = None,
    renderer: FakeRenderer | None = None,
    topology_renderer: FakeTopologyRenderer | None = None,
    health_renderer: FakeHealthRenderer | None = None,
    action_renderer: FakeActionPlanRenderer | None = None,
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    runtime = runtime if runtime is not None else FakeRuntime()
    renderer = renderer if renderer is not None else FakeRenderer()
    topology_renderer = (
        topology_renderer if topology_renderer is not None else FakeTopologyRenderer()
    )
    health_renderer = health_renderer if health_renderer is not None else FakeHealthRenderer()
    action_renderer = (
        action_renderer if action_renderer is not None else FakeActionPlanRenderer()
    )

    with patch("zorix.cli._create_runtime", return_value=runtime):
        with patch("zorix.cli._create_renderer", return_value=renderer):
            with patch("zorix.cli._create_topology_renderer", return_value=topology_renderer):
                with patch("zorix.cli._create_health_renderer", return_value=health_renderer):
                    with patch("zorix.cli._create_action_plan_renderer", return_value=action_renderer):
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
