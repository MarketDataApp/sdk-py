from logging import DEBUG, Logger

from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def get_retry_adapter(
    attempts: int,
    backoff: float,
    logger: Logger,
    exceptions: list[Exception] = None,
    reraise: bool = False,
    min_backoff: float = 0.5,
    max_backoff: float = 5,
) -> Retrying:

    if not exceptions:
        exceptions = [Exception]

    return Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=backoff, min=min_backoff, max=max_backoff),
        retry=retry_if_exception_type(*exceptions),
        reraise=reraise,
        before_sleep=before_sleep_log(logger, log_level=DEBUG),
    )
