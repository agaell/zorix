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


class ActionExecutionEngineError(RuntimeError):
    pass


class InvalidActionExecutorOutputError(ActionExecutionEngineError):
    def __init__(self, executor: str, reason: str) -> None:
        self.executor = executor
        self.reason = reason
        super().__init__(f"Action executor {executor} returned invalid output: {reason}")


class ActionExecutorNotFoundError(ActionExecutionEngineError):
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Action executor was not found: {provider}")


class AmbiguousActionExecutorError(ActionExecutionEngineError):
    def __init__(self, provider: str, executor_count: int) -> None:
        self.provider = provider
        self.executor_count = executor_count
        super().__init__(
            f"Multiple action executors are registered for {provider}: {executor_count}"
        )
