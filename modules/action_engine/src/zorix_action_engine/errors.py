from __future__ import annotations


class ActionEngineError(RuntimeError):
    pass


class InvalidActionProviderOutputError(ActionEngineError):
    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(f"Action provider {provider} returned invalid output: {reason}")


class AmbiguousActionProviderError(ActionEngineError):
    def __init__(self, action: str, resource_id: str, provider_count: int) -> None:
        self.action = action
        self.resource_id = resource_id
        self.provider_count = provider_count
        super().__init__(
            f"Multiple action providers support {action} for {resource_id}: {provider_count}"
        )
