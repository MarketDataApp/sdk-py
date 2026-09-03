from functools import wraps
from logging import DEBUG
from typing import TYPE_CHECKING, Callable

from tenacity import before_sleep_log

from marketdata.api_status import API_STATUS_DATA, APIStatusResult
from marketdata.exceptions import RequestError
from marketdata.internal_settings import INITIAL_RETRY_DELAY
from marketdata.resources.base import BaseResource
from marketdata.retry import get_retry_adapter

if TYPE_CHECKING:
    from marketdata.client import MarketDataClient


def api_error_handler(
    func: Callable = None, service: str = None, check_status: bool = True
) -> Callable:
    if func is None:
        return lambda f: api_error_handler(
            f, service=service, check_status=check_status
        )

    @wraps(func)
    def wrapper(*args, **kwargs):
        resource: BaseResource = args[0]
        client: "MarketDataClient" = resource.client
        logger = client.logger
        log_before_sleep = before_sleep_log(logger, log_level=DEBUG)

        def _status_check_before_sleep(retry_state):
            # Endpoints outside /v1/ (the utilities) have no entry in the
            # /status/ service list, so they opt out of the check.
            if check_status:
                status = API_STATUS_DATA.get_api_status(client, service)
                if status == APIStatusResult.OFFLINE:
                    raise retry_state.outcome.exception()
            log_before_sleep(retry_state)

        retry_adapter = get_retry_adapter(
            attempts=client.max_retries + 1,
            initial_delay=INITIAL_RETRY_DELAY,
            exceptions=[RequestError],
            logger=logger,
            reraise=True,
            before_sleep=_status_check_before_sleep,
        )
        return retry_adapter(func, *args, **kwargs)

    return wrapper
