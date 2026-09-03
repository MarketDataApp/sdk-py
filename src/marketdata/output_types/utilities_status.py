import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class ServiceStatus:
    """Status of one API service, one row of ``GET /status/``."""

    service: str
    status: str
    online: bool
    uptimePct30d: float
    uptimePct90d: float
    updated: datetime.datetime

    def __post_init__(self):
        self.updated = format_timestamp(self.updated)

    @property
    def is_online(self) -> bool:
        return self.online and self.status == "online"

    def __repr__(self) -> str:
        return (
            f"Service Status: {self.service} {self.status}"
            f" (30d: {self.uptimePct30d:.2%}, 90d: {self.uptimePct90d:.2%}),"
            f" Updated: {self.updated}"
        )

    def __str__(self) -> str:
        return self.__repr__()
