from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from logging import DEBUG, Logger
from typing import Callable

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
)


def parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header (RFC 7231 §7.1.3).

    Accepts delta-seconds or HTTP-date. Returns None when the value is
    missing or unparseable so callers can fall back to their default wait.
    """
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if target is None:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())


def get_retry_adapter(
    attempts: int,
    initial_delay: float,
    logger: Logger,
    exceptions: list[Exception] = None,
    reraise: bool = False,
    before_sleep: Callable = None,
) -> Retrying:

    if not exceptions:
        exceptions = [Exception]

    def _compute_wait(retry_state) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if exc is not None:
            response = getattr(exc, "response", None)
            if response is not None:
                retry_after = parse_retry_after(
                    response.headers.get("Retry-After")
                )
                if retry_after is not None:
                    return retry_after
        return initial_delay * 2 ** (retry_state.attempt_number - 1)

    return Retrying(
        stop=stop_after_attempt(attempts),
        wait=_compute_wait,
        retry=retry_if_exception_type(tuple(exceptions)),
        reraise=reraise,
        before_sleep=before_sleep or before_sleep_log(logger, log_level=DEBUG),
    )
