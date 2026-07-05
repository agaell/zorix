from dataclasses import dataclass


@dataclass
class Event:
    id: str
    type: str
    resource_id: str
    message: str
