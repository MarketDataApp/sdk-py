import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class UserRateLimits:
    """The account's API-credit state, read from the ``x-api-ratelimit-*``
    headers of the last response (SDK requirements §8.1)."""

    credit_limit: int
    credits_remaining: int
    reset_time: datetime.datetime
    credits_consumed: int

    def __post_init__(self):
        self.reset_time = format_timestamp(self.reset_time)

    def __repr__(self) -> str:
        return (
            f"Credits used {self.credits_consumed}/{self.credit_limit}, "
            f"remaining: {self.credits_remaining}, "
            f"reset at: {self.reset_time.isoformat()}"
        )

    def __str__(self) -> str:
        return self.__repr__()
