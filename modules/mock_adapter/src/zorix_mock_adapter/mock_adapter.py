from dataclasses import dataclass, field

from zorix_core_model import Adapter, Resource


def _default_resources() -> list[Resource]:
    return [
        Resource(
            id="mock-service-1",
            type="service",
            name="mock-api",
            state="active",
            metadata={"description": "Predefined mock API service"},
            labels={"environment": "mock"},
        ),
        Resource(
            id="mock-service-2",
            type="service",
            name="mock-worker",
            state="active",
            metadata={"description": "Predefined mock worker service"},
            labels={"environment": "mock"},
        ),
        Resource(
            id="mock-container-1",
            type="container",
            name="mock-runtime",
            state="active",
            metadata={"description": "Predefined mock container"},
            labels={"environment": "mock"},
        ),
        Resource(
            id="mock-user-1",
            type="user",
            name="mock-admin",
            state="active",
            metadata={"role": "admin"},
            labels={"environment": "mock"},
        ),
        Resource(
            id="mock-user-2",
            type="user",
            name="mock-reader",
            state="inactive",
            metadata={"role": "reader"},
            labels={"environment": "mock"},
        ),
    ]


@dataclass
class MockAdapter(Adapter):
    resources: list[Resource] = field(default_factory=_default_resources)

    def discover(self) -> list[Resource]:
        return list(self.resources)
