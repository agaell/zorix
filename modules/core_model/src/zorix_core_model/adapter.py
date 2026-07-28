from abc import ABC, abstractmethod

from .resource import Resource


class Adapter(ABC):
    @abstractmethod
    def discover(self) -> list[Resource]:
        ...
