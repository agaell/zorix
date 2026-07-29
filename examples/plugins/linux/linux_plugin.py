import os

from zorix_linux_adapter import LinuxAdapter


class ConfiguredLinuxAdapter(LinuxAdapter):
    def __init__(self) -> None:
        super().__init__(target=os.environ.get("ZORIX_SSH_TARGET", ""))


Adapter = ConfiguredLinuxAdapter

__all__ = ["Adapter"]
