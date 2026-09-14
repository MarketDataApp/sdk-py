import datetime
from dataclasses import dataclass

from pytz.exceptions import InvalidTimeError

from marketdata.utils import DEFAULT_TIMEZONE, format_timestamp


@dataclass
class UserRateLimits:
    """The account's API-credit state, read from the ``x-api-ratelimit-*``
    headers of the last response (SDK requirements §8.1)."""

    credit_limit: int
    credits_remaining: int
    reset_time: datetime.datetime
    credits_consumed: int

    def __post_init__(self):
        """Settle the timezone once, so the state holds one instant.

        A value that arrives without an offset is US/Eastern, the timezone
        every other timestamp in the SDK is rendered in and the one
        ``format_timestamp`` leaves implicit when it parses a date with no
        offset. Reading it as UTC put the value hours away from what it meant,
        which the pre-flight check turns into a refusal that is early or late
        by that much (#42).

        Settling it here rather than on each read is what makes the rendered
        value and the compared value the same: ``__repr__``, the client's log
        and error messages and ``get_meta(...).rate_limits.reset_time`` all
        carry the offset, and ``localize`` runs one time per state instead of
        on every read.
        """
        reset_time = format_timestamp(self.reset_time)
        if reset_time.tzinfo is None:
            try:
                # `is_dst=None`: a wall time a DST change repeats or skips
                # names no single instant. Picking one silently puts the reset
                # an hour from what the caller meant, so say so instead.
                reset_time = DEFAULT_TIMEZONE.localize(reset_time, is_dst=None)
            except InvalidTimeError as exc:
                raise ValueError(
                    f"{reset_time.isoformat()} is not one US/Eastern time: a "
                    "daylight-saving change repeats or skips it. Pass a value "
                    "that carries its own offset."
                ) from exc
        self.reset_time = reset_time

    @property
    def reset_timestamp(self) -> float:
        """``reset_time`` as a POSIX timestamp, so two states can be ordered."""
        return self.reset_time.timestamp()

    def __repr__(self) -> str:
        return (
            f"Credits used {self.credits_consumed}/{self.credit_limit}, "
            f"remaining: {self.credits_remaining}, "
            f"reset at: {self.reset_time.isoformat()}"
        )

    def __str__(self) -> str:
        return self.__repr__()
