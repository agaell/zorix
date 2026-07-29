from __future__ import annotations

from zorix_health_engine import HealthProviderError, HealthResult
from zorix_health_model import HealthFinding


class HealthConsoleRenderer:
    def render(self, result: HealthResult) -> str:
        lines = _summary_lines(result)
        sections: list[list[str]] = []

        if result.findings:
            sections.append(
                ["Findings:", *[self._format_finding(finding) for finding in result.findings]]
            )

        if result.errors:
            sections.append(
                ["Errors:", *[self._format_error(error) for error in result.errors]]
            )

        for section in sections:
            lines.append("")
            lines.extend(section)

        return "\n".join(lines) + "\n"

    def _format_finding(self, finding: HealthFinding) -> str:
        return (
            f"- {finding.severity.value} {finding.code}: "
            f"{finding.message} [{finding.resource_id}]"
        )

    def _format_error(self, error: HealthProviderError) -> str:
        message = error.message.strip()
        if message:
            return f"- {error.provider}: {error.error_type}: {message}"

        return f"- {error.provider}: {error.error_type}"


def _summary_lines(result: HealthResult) -> list[str]:
    return [
        f"Health evaluation: {result.status.value}",
        f"Health: {result.level.value}",
        f"Providers: {result.provider_count}",
        f"Successful providers: {result.successful_provider_count}",
        f"Failed providers: {result.failed_provider_count}",
        f"Resources evaluated: {result.resource_count}",
        f"Findings: {result.finding_count}",
        f"Critical: {result.critical_count}",
        f"Warnings: {result.warning_count}",
        f"Info: {result.info_count}",
    ]
