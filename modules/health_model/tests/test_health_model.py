from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from zorix_health_model import (
    HealthFinding,
    HealthLevel,
    HealthSeverity,
    health_level_for_findings,
    severity_rank,
)


class HealthModelTest(unittest.TestCase):
    def test_severity_enums(self) -> None:
        self.assertEqual(HealthSeverity.INFO.value, "INFO")
        self.assertEqual(HealthSeverity.WARNING.value, "WARNING")
        self.assertEqual(HealthSeverity.CRITICAL.value, "CRITICAL")
        self.assertLess(severity_rank(HealthSeverity.INFO), severity_rank(HealthSeverity.WARNING))
        self.assertLess(severity_rank(HealthSeverity.WARNING), severity_rank(HealthSeverity.CRITICAL))

    def test_health_level_enums(self) -> None:
        self.assertEqual(HealthLevel.HEALTHY.value, "HEALTHY")
        self.assertEqual(HealthLevel.WARNING.value, "WARNING")
        self.assertEqual(HealthLevel.CRITICAL.value, "CRITICAL")

    def test_health_finding_is_immutable(self) -> None:
        finding = _finding()

        with self.assertRaises(FrozenInstanceError):
            finding.message = "changed"  # type: ignore[misc]

    def test_identity(self) -> None:
        self.assertEqual(_finding().identity, ("linux", "linux.service.failed", "r1"))

    def test_metadata_is_read_only_and_not_part_of_equality_or_hash(self) -> None:
        first = _finding(metadata={"value": "first"})
        second = _finding(metadata={"value": "second"})

        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))
        with self.assertRaises(TypeError):
            first.metadata["value"] = "changed"  # type: ignore[index]

    def test_external_string_whitespace_is_normalized(self) -> None:
        finding = HealthFinding(
            source=" linux ",
            code=" linux.code ",
            severity=HealthSeverity.INFO,
            resource_id=" resource ",
            message=" message ",
        )

        self.assertEqual(finding.source, "linux")
        self.assertEqual(finding.code, "linux.code")
        self.assertEqual(finding.resource_id, "resource")
        self.assertEqual(finding.message, "message")

    def test_empty_required_strings_are_rejected(self) -> None:
        for field_name in ("source", "code", "resource_id", "message"):
            values = {
                "source": "linux",
                "code": "code",
                "severity": HealthSeverity.INFO,
                "resource_id": "r1",
                "message": "message",
            }
            values[field_name] = "   "
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValueError):
                    HealthFinding(**values)  # type: ignore[arg-type]

    def test_invalid_severity_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            HealthFinding("linux", "code", "WARNING", "r1", "message")  # type: ignore[arg-type]

    def test_metadata_types_are_validated(self) -> None:
        with self.assertRaises(ValueError):
            _finding(metadata=[("key", "value")])  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            _finding(metadata={1: "value"})  # type: ignore[dict-item]
        with self.assertRaises(ValueError):
            _finding(metadata={"key": 1})  # type: ignore[dict-item]

    def test_health_level_for_findings(self) -> None:
        self.assertIs(health_level_for_findings(()), HealthLevel.HEALTHY)
        self.assertIs(health_level_for_findings((_finding(severity=HealthSeverity.INFO),)), HealthLevel.HEALTHY)
        self.assertIs(health_level_for_findings((_finding(severity=HealthSeverity.WARNING),)), HealthLevel.WARNING)
        self.assertIs(health_level_for_findings((_finding(severity=HealthSeverity.CRITICAL),)), HealthLevel.CRITICAL)


def _finding(
    *,
    severity: HealthSeverity = HealthSeverity.WARNING,
    metadata: object | None = None,
) -> HealthFinding:
    return HealthFinding(
        source="linux",
        code="linux.service.failed",
        severity=severity,
        resource_id="r1",
        message="message",
        metadata={} if metadata is None else metadata,  # type: ignore[arg-type]
    )


if __name__ == "__main__":
    unittest.main()
