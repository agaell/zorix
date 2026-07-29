from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import unittest

from zorix_health_engine import HealthProviderError, HealthResult, HealthStatus
from zorix_health_model import HealthFinding, HealthLevel, HealthSeverity
from zorix_presentation import HealthConsoleRenderer


class HealthConsoleRendererTest(unittest.TestCase):
    def test_healthy(self) -> None:
        text = HealthConsoleRenderer().render(_result())

        self.assertEqual(
            text,
            "Health evaluation: SUCCESS\n"
            "Health: HEALTHY\n"
            "Providers: 1\n"
            "Successful providers: 1\n"
            "Failed providers: 0\n"
            "Resources evaluated: 2\n"
            "Findings: 0\n"
            "Critical: 0\n"
            "Warnings: 0\n"
            "Info: 0\n",
        )

    def test_warning_and_critical_counts(self) -> None:
        text = HealthConsoleRenderer().render(
            _result(
                findings=(
                    _finding("warning", HealthSeverity.WARNING),
                    _finding("critical", HealthSeverity.CRITICAL),
                    _finding("info", HealthSeverity.INFO),
                )
            )
        )

        self.assertIn("Health: CRITICAL\n", text)
        self.assertIn("Findings: 3\n", text)
        self.assertIn("Critical: 1\n", text)
        self.assertIn("Warnings: 1\n", text)
        self.assertIn("Info: 1\n", text)

    def test_partial_and_failed_status(self) -> None:
        partial = HealthConsoleRenderer().render(
            _result(
                status=HealthStatus.PARTIAL,
                errors=(HealthProviderError("example.Provider", "RuntimeError", "failed"),),
                provider_count=2,
                successful_provider_count=1,
            )
        )
        failed = HealthConsoleRenderer().render(
            _result(
                status=HealthStatus.FAILED,
                errors=(HealthProviderError("example.Provider", "RuntimeError", "failed"),),
                provider_count=1,
                successful_provider_count=0,
            )
        )

        self.assertIn("Health evaluation: PARTIAL\n", partial)
        self.assertIn("Failed providers: 1\n", partial)
        self.assertIn("Health evaluation: FAILED\n", failed)

    def test_finding_order_and_no_metadata(self) -> None:
        result = _result(
            findings=(
                _finding("first", HealthSeverity.WARNING, metadata={"hidden": "value"}),
                _finding("second", HealthSeverity.CRITICAL),
            )
        )

        text = HealthConsoleRenderer().render(result)

        self.assertLess(text.index("test.first"), text.index("test.second"))
        self.assertNotIn("hidden", text)
        self.assertIn("- WARNING test.first: message first [first]\n", text)

    def test_error_order_and_empty_message(self) -> None:
        result = _result(
            status=HealthStatus.PARTIAL,
            errors=(
                HealthProviderError("example.First", "RuntimeError", "first"),
                HealthProviderError("example.Second", "ValueError", ""),
            ),
            provider_count=3,
            successful_provider_count=1,
        )

        text = HealthConsoleRenderer().render(result)

        self.assertLess(text.index("example.First"), text.index("example.Second"))
        self.assertIn("- example.First: RuntimeError: first\n", text)
        self.assertIn("- example.Second: ValueError\n", text)

    def test_no_print(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            HealthConsoleRenderer().render(_result())

        self.assertEqual(stdout.getvalue(), "")

    def test_exactly_one_final_newline_and_no_triple_newline(self) -> None:
        text = HealthConsoleRenderer().render(
            _result(findings=(_finding("first", HealthSeverity.INFO),))
        )

        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))
        self.assertNotIn("\n\n\n", text)

    def test_repeated_render_identical_and_result_not_changed(self) -> None:
        result = _result(findings=(_finding("first", HealthSeverity.INFO),))
        before = (result.status, result.level, result.findings, result.errors)
        renderer = HealthConsoleRenderer()

        first = renderer.render(result)
        second = renderer.render(result)

        self.assertEqual(first, second)
        self.assertEqual((result.status, result.level, result.findings, result.errors), before)


def _result(
    *,
    status: HealthStatus = HealthStatus.SUCCESS,
    findings: tuple[HealthFinding, ...] = (),
    errors: tuple[HealthProviderError, ...] = (),
    provider_count: int = 1,
    successful_provider_count: int = 1,
) -> HealthResult:
    level = HealthLevel.HEALTHY
    if any(finding.severity is HealthSeverity.CRITICAL for finding in findings):
        level = HealthLevel.CRITICAL
    elif any(finding.severity is HealthSeverity.WARNING for finding in findings):
        level = HealthLevel.WARNING

    return HealthResult(
        status=status,
        level=level,
        findings=findings,
        errors=errors,
        provider_count=provider_count,
        successful_provider_count=successful_provider_count,
        resource_count=2,
    )


def _finding(
    resource_id: str,
    severity: HealthSeverity,
    *,
    metadata: dict[str, str] | None = None,
) -> HealthFinding:
    return HealthFinding(
        "test",
        f"test.{resource_id}",
        severity,
        resource_id,
        f"message {resource_id}",
        metadata={} if metadata is None else metadata,
    )


if __name__ == "__main__":
    unittest.main()
