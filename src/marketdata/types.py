import datetime
from dataclasses import dataclass

import pytz

from marketdata.utils import format_timestamp

# Every timestamp the SDK renders is US/Eastern, so a value that arrived
# without an offset is read in that zone rather than in UTC.
DEFAULT_TIMEZONE = pytz.timezone("US/Eastern")


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

    @property
    def reset_timestamp(self) -> float:
        """``reset_time`` as a POSIX timestamp, so two states can be ordered
        whatever their timezone awareness.

        A naive value reads as US/Eastern, the timezone every other timestamp
        in the SDK is rendered in and the one ``format_timestamp`` leaves
        implicit when it parses a date with no offset. Reading it as UTC put
        the value hours away from what it meant, which the pre-flight check
        turns into a refusal that is early or late by that much (#42).
        """
        reset = self.reset_time
        if reset.tzinfo is None:
            reset = DEFAULT_TIMEZONE.localize(reset)
        return reset.timestamp()

    def __repr__(self) -> str:
        return (
            f"Credits used {self.credits_consumed}/{self.credit_limit}, "
            f"remaining: {self.credits_remaining}, "
            f"reset at: {self.reset_time.isoformat()}"
        )

    def __str__(self) -> str:
        return self.__repr__()
