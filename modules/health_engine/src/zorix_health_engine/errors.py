from __future__ import annotations


class HealthEngineError(RuntimeError):
    pass


class InvalidHealthProviderOutputError(HealthEngineError):
    def __init__(self, provider: str, actual_type: str) -> None:
        self.provider = provider
        self.actual_type = actual_type
        super().__init__(
            f"Health provider {provider} returned {actual_type}; expected list[HealthFinding]"
        )
