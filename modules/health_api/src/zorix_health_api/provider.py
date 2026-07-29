from __future__ import annotations

from typing import Protocol, runtime_checkable

from zorix_health_model import HealthFinding

from .context import HealthContext


@runtime_checkable
class HealthProvider(Protocol):
    def evaluate_health(
        self,
        context: HealthContext,
    ) -> list[HealthFinding]:
        ...
