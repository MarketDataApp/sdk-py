from logging import DEBUG, Logger
from typing import Callable

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
)


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
        # 9.4 hook: read Retry-After from
        # retry_state.outcome.exception().response.headers and override here
        # before falling back to the exponential formula.
        return initial_delay * 2 ** (retry_state.attempt_number - 1)

    return Retrying(
        stop=stop_after_attempt(attempts),
        wait=_compute_wait,
        retry=retry_if_exception_type(tuple(exceptions)),
        reraise=reraise,
        before_sleep=before_sleep or before_sleep_log(logger, log_level=DEBUG),
    )
