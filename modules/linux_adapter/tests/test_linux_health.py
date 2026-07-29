from __future__ import annotations

import unittest

from zorix_core_model import Resource
from zorix_health_api import HealthContext, HealthProvider
from zorix_health_model import HealthSeverity
from zorix_linux_adapter import LinuxAdapter


class FailingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], str | None]] = []

    def run(
        self,
        target: str,
        arguments: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> str:
        self.calls.append((target, tuple(arguments), input_text))
        raise AssertionError("SSH must not be called")


class LinuxHealthTest(unittest.TestCase):
    def test_linux_adapter_is_health_provider(self) -> None:
        self.assertIsInstance(LinuxAdapter("test-host"), HealthProvider)

    def test_empty_context(self) -> None:
        self.assertEqual(_adapter().evaluate_health(HealthContext([])), [])

    def test_failed_service_by_resource_state(self) -> None:
        finding = _evaluate(_service("nginx.service", state=" failed "))[0]

        self.assertEqual(finding.code, "linux.service.failed")
        self.assertIs(finding.severity, HealthSeverity.CRITICAL)
        self.assertEqual(finding.message, "Service nginx.service is failed")
        self.assertEqual(finding.resource_id, "linux:service:tandem:nginx.service")

    def test_failed_service_by_active_state(self) -> None:
        finding = _evaluate(_service("nginx.service", active_state="failed"))[0]

        self.assertIs(finding.severity, HealthSeverity.CRITICAL)

    def test_failed_service_by_sub_state(self) -> None:
        finding = _evaluate(_service("nginx.service", sub_state="failed"))[0]

        self.assertIs(finding.severity, HealthSeverity.CRITICAL)

    def test_service_has_one_finding(self) -> None:
        findings = _evaluate(
            _service(
                "nginx.service",
                state="failed",
                active_state="failed",
                sub_state="failed",
            )
        )

        self.assertEqual(len(findings), 1)

    def test_inactive_and_dead_services_are_not_findings(self) -> None:
        for state in ("inactive", "dead", "exited", "activating", "deactivating"):
            with self.subTest(state=state):
                self.assertEqual(_evaluate(_service("nginx.service", state=state)), [])

    def test_filesystem_thresholds(self) -> None:
        cases = (
            (79, None),
            (80, HealthSeverity.WARNING),
            (89, HealthSeverity.WARNING),
            (90, HealthSeverity.CRITICAL),
            (100, HealthSeverity.CRITICAL),
        )

        for usage_percent, severity in cases:
            with self.subTest(usage_percent=usage_percent):
                findings = _evaluate(_filesystem("/", usage_percent))
                if severity is None:
                    self.assertEqual(findings, [])
                else:
                    self.assertEqual(len(findings), 1)
                    self.assertIs(findings[0].severity, severity)
                    self.assertEqual(
                        findings[0].message,
                        f"Filesystem / usage is {usage_percent}%",
                    )

    def test_malformed_filesystem_percentage_is_skipped(self) -> None:
        self.assertEqual(_evaluate(_filesystem("/", "84%")), [])
        self.assertEqual(_evaluate(_filesystem("/", "-1")), [])
        self.assertEqual(_evaluate(_filesystem("/", "101")), [])

    def test_memory_thresholds(self) -> None:
        cases = (
            (21, None),
            (20, HealthSeverity.WARNING),
            (10, HealthSeverity.CRITICAL),
            (8, HealthSeverity.CRITICAL),
        )

        for available_percent, severity in cases:
            with self.subTest(available_percent=available_percent):
                findings = _evaluate(_memory(available_percent))
                if severity is None:
                    self.assertEqual(findings, [])
                else:
                    self.assertEqual(len(findings), 1)
                    self.assertIs(findings[0].severity, severity)
                    self.assertEqual(
                        findings[0].message,
                        f"Available memory is {available_percent:.2f}% of total",
                    )
                    self.assertEqual(findings[0].metadata["available_percent"], f"{available_percent:.2f}")

    def test_memory_available_greater_than_total_is_skipped(self) -> None:
        self.assertEqual(_evaluate(_memory_raw(total_bytes="100", available_bytes="101")), [])

    def test_memory_total_zero_is_skipped(self) -> None:
        self.assertEqual(_evaluate(_memory_raw(total_bytes="0", available_bytes="0")), [])

    def test_foreign_target_namespace_and_host_id_are_ignored(self) -> None:
        self.assertEqual(_evaluate(_service("nginx.service", state="failed", target="other")), [])
        self.assertEqual(
            _evaluate(Resource("docker:service:tandem:nginx.service", "service", "nginx.service", "failed")),
            [],
        )
        self.assertEqual(
            _evaluate(_service("nginx.service", state="failed", host_id="linux:host:other")),
            [],
        )

    def test_socket_does_not_create_finding(self) -> None:
        socket = Resource(
            "linux:socket:tandem:tcp:0.0.0.0:443",
            "socket",
            "tcp://0.0.0.0:443",
            "listening",
            metadata={"host_id": "linux:host:tandem"},
        )

        self.assertEqual(_evaluate(socket), [])

    def test_runner_is_not_called(self) -> None:
        runner = FailingRunner()
        adapter = LinuxAdapter("tandem", runner)

        adapter.evaluate_health(HealthContext([_service("nginx.service", state="failed")]))

        self.assertEqual(runner.calls, [])

    def test_resource_order_is_preserved(self) -> None:
        resources = [
            _service("first.service", state="failed"),
            _filesystem("/", 84),
            _memory(10),
        ]

        findings = _evaluate(*resources)

        self.assertEqual(
            [finding.resource_id for finding in findings],
            [
                "linux:service:tandem:first.service",
                "linux:filesystem:tandem:%2F",
                "linux:memory:tandem",
            ],
        )

    def test_repeated_evaluate_is_identical(self) -> None:
        adapter = _adapter()
        context = HealthContext([_service("nginx.service", state="failed")])

        first = adapter.evaluate_health(context)
        second = adapter.evaluate_health(context)

        self.assertEqual(first, second)


def _adapter() -> LinuxAdapter:
    return LinuxAdapter("tandem", FailingRunner())


def _evaluate(*resources: Resource) -> list:
    return _adapter().evaluate_health(HealthContext(resources))


def _service(
    unit: str,
    *,
    state: str = "active",
    active_state: str = "active",
    sub_state: str = "running",
    target: str = "tandem",
    host_id: str = "linux:host:tandem",
) -> Resource:
    return Resource(
        f"linux:service:{target}:{unit}",
        "service",
        unit,
        state,
        metadata={
            "host_id": host_id,
            "unit": unit,
            "active_state": active_state,
            "sub_state": sub_state,
        },
    )


def _filesystem(mountpoint: str, usage_percent: int | str) -> Resource:
    return Resource(
        "linux:filesystem:tandem:%2F",
        "filesystem",
        mountpoint,
        "mounted",
        metadata={
            "host_id": "linux:host:tandem",
            "mountpoint": mountpoint,
            "usage_percent": str(usage_percent),
            "available_bytes": "20",
            "size_bytes": "100",
        },
    )


def _memory(available_percent: int) -> Resource:
    return _memory_raw(total_bytes="100", available_bytes=str(available_percent))


def _memory_raw(*, total_bytes: str, available_bytes: str) -> Resource:
    return Resource(
        "linux:memory:tandem",
        "memory",
        "System memory",
        "present",
        metadata={
            "host_id": "linux:host:tandem",
            "total_bytes": total_bytes,
            "available_bytes": available_bytes,
        },
    )


if __name__ == "__main__":
    unittest.main()
