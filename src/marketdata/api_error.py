from functools import wraps
from typing import TYPE_CHECKING, Callable

from marketdata.api_status import API_STATUS_DATA, APIStatusResult
from marketdata.exceptions import RequestError
from marketdata.internal_settings import (
    MAX_RETRY_ATTEMPTS,
    MAX_RETRY_BACKOFF,
    MIN_RETRY_BACKOFF,
    RETRY_BACKOFF,
)
from marketdata.resources.base import BaseResource
from marketdata.retry import get_retry_adapter

if TYPE_CHECKING:
    from marketdata.client import MarketDataClient


def api_error_handler(func: Callable = None, service: str = None) -> Callable:
    if func is None:
        return lambda f: api_error_handler(f, service=service)

    @wraps(func)
    def wrapper(*args, **kwargs):
        resource: BaseResource = args[0]
        client: "MarketDataClient" = resource.client
        logger = client.logger

        try:
            return func(*args, **kwargs)
        except RequestError as e:
            if API_STATUS_DATA.should_refresh:
                API_STATUS_DATA.refresh(client)

            status = API_STATUS_DATA.get_api_status(client, service)
            if status in (APIStatusResult.ONLINE, APIStatusResult.UNKNOWN):
                retry_adapter = get_retry_adapter(
                    attempts=MAX_RETRY_ATTEMPTS,
                    backoff=RETRY_BACKOFF,
                    exceptions=[RequestError],
                    logger=logger,
                    reraise=True,
                    min_backoff=MIN_RETRY_BACKOFF,
                    max_backoff=MAX_RETRY_BACKOFF,
                )
                return retry_adapter(func, *args, **kwargs)
            raise e

    return wrapper
