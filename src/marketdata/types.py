import datetime
from dataclasses import dataclass

from pytz.exceptions import InvalidTimeError

from marketdata.utils import DEFAULT_TIMEZONE


@dataclass
class UserRateLimits:
    """The account's API-credit state, read from the ``x-api-ratelimit-*``
    headers of the last response (SDK requirements §8.1)."""

    credit_limit: int
    credits_remaining: int
    reset_time: datetime.datetime
    credits_consumed: int

    def __post_init__(self):
        """Settle ``reset_time`` as one US/Eastern instant.

        A number, or a numeric string such as the ``x-api-ratelimit-reset``
        header, is Unix seconds. A datetime without an offset is US/Eastern.

        Raises:
            ValueError: If ``reset_time`` is neither a datetime nor Unix
                seconds, or is a wall time a daylight-saving change repeats or
                skips.
        """
        reset_time = self.reset_time
        if not isinstance(reset_time, datetime.datetime):
            try:
                reset_time = datetime.datetime.fromtimestamp(
                    float(reset_time), tz=DEFAULT_TIMEZONE
                )
            except (TypeError, ValueError, OverflowError, OSError):
                raise ValueError(
                    f"reset_time is neither a datetime nor Unix seconds: {reset_time!r}"
                ) from None
        if reset_time.tzinfo is None:
            try:
                # `is_dst=None`: a repeated or skipped wall time names no single
                # instant, and picking one would move the reset by an hour.
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
