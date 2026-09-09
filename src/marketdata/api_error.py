from functools import wraps
from logging import DEBUG
from typing import TYPE_CHECKING, Callable

from httpx import LocalProtocolError, ProxyError, UnsupportedProtocol
from tenacity import Retrying, before_sleep_log

from marketdata.api_status import API_STATUS_DATA, APIStatusResult
from marketdata.exceptions import NetworkError, ServerError
from marketdata.internal_settings import INITIAL_RETRY_DELAY
from marketdata.meta import ResponseMeta, attach_meta, collect_metas
from marketdata.resources.base import BaseResource
from marketdata.retry import get_retry_adapter

if TYPE_CHECKING:
    from marketdata.client import MarketDataClient


# Transport failures the client itself caused: a base URL without a scheme, a
# malformed request (a token with a trailing newline), a proxy that refuses the
# connection. They fail the same way on every attempt, so they are not retried.
NON_RETRYABLE_TRANSPORT_ERRORS = (LocalProtocolError, ProxyError, UnsupportedProtocol)


def should_retry(exc: BaseException) -> bool:
    """SDK requirements §9.2: retry ``ServerError`` (501 and above) and
    ``NetworkError`` unless the client caused it; never a 4xx, an
    ``InternalError`` (500) or a rate limit."""
    if isinstance(exc, NetworkError):
        return not isinstance(exc.__cause__, NON_RETRYABLE_TRANSPORT_ERRORS)
    return isinstance(exc, ServerError)


def get_resource_retry_adapter(
    client: "MarketDataClient", service: str, check_status: bool = True
) -> Retrying:
    """The retry policy every resource applies to one request: the first
    attempt plus ``client.max_retries``, exponential backoff, only the
    failures ``should_retry`` accepts, and a look at the service status
    before each wait (an OFFLINE service stops the retries).

    The single-request resources get it through ``api_error_handler``; the
    fan-out resources build one and retry each request on its own (#83).
    """
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

    return get_retry_adapter(
        attempts=client.max_retries + 1,
        initial_delay=INITIAL_RETRY_DELAY,
        should_retry=should_retry,
        logger=logger,
        reraise=True,
        before_sleep=_status_check_before_sleep,
    )


def api_error_handler(
    func: Callable = None,
    service: str = None,
    check_status: bool = True,
    retry: bool = True,
) -> Callable:
    """Wrap a resource method: retry it (``retry=True``), log the terminal
    failure once and attach the response metadata to the result.

    ``retry=False`` is for the resources that issue several requests per call
    and retry each one on their own with ``get_resource_retry_adapter``: a
    second retry around the whole call would re-send every healthy request
    for each failed one (#83).
    """
    if func is None:
        return lambda f: api_error_handler(
            f, service=service, check_status=check_status, retry=retry
        )

    @wraps(func)
    def wrapper(*args, **kwargs):
        resource: BaseResource = args[0]
        client: "MarketDataClient" = resource.client
        logger = client.logger

        def call():
            if not retry:
                return func(*args, **kwargs)
            retry_adapter = get_resource_retry_adapter(
                client, service, check_status=check_status
            )
            return retry_adapter(func, *args, **kwargs)

        # Every response behind this call (chunks, symbols, retried attempts)
        # lands in `metas`; the merged metadata travels with the result (#49).
        with collect_metas() as metas:
            try:
                result = call()
            except Exception as exc:
                # Terminal failure, retries included: one ERROR line (SDK
                # requirements §7), then the caller gets the exception itself.
                logger.error(f"{func.__name__} failed: {exc}")
                # A failed call is billed too: the responses it did get, the
                # healthy requests of a fan-out and every retried attempt all
                # consumed credits. `get_meta(exc)` reads them back, so the
                # caller can account for what a failure cost.
                if metas:
                    attach_meta(exc, ResponseMeta.merge(metas))
                raise
        if not metas:  # pragma: no cover - every resource call answers
            return result
        return attach_meta(result, ResponseMeta.merge(metas))

    return wrapper
