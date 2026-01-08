import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class UserRateLimits:
    requests_limit: int
    requests_remaining: int
    requests_reset: datetime.datetime
    requests_consumed: int

    def __post_init__(self):
        self.requests_reset = format_timestamp(self.requests_reset)

    def __repr__(self) -> str:
        return f"Rate used {self.requests_consumed}/{self.requests_limit},\
            remaining: {self.requests_remaining} credits,\
            next reset: {self.requests_reset.isoformat()}"

    def __str__(self) -> str:
        return self.__repr__()
