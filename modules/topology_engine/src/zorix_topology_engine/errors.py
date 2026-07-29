from __future__ import annotations


class TopologyEngineError(RuntimeError):
    pass


class InvalidTopologyProviderOutputError(TopologyEngineError):
    def __init__(self, provider: str, actual_type: str) -> None:
        self.provider = provider
        self.actual_type = actual_type
        super().__init__(
            f"Topology provider {provider} returned {actual_type}; expected list"
        )
