"""Exceptions for the MarketData Python SDK.

Every resource method raises on failure (SDK requirements §6.4). Every
exception carries the support context of §6.2 and renders it through
``support_info`` (§6.3), so a caller can paste one block into a support ticket.

The HTTP classes follow the taxonomy of §6.1 and the status mapping of §9.1:

==============  ==========================================================
status          exception
==============  ==========================================================
400             ``BadRequestError``
401             ``AuthenticationError`` (never retried)
403             ``ForbiddenError``
404 + errmsg    ``NotFoundError``
404 no_data     no exception: the resource returns an empty result
429             ``RateLimitError`` (never retried, carries ``retry_after``)
500             ``ServerError`` (not retried)
501 to 599      ``ServerError`` (retried with exponential backoff)
transport       ``NetworkError`` (retried)
bad JSON body   ``ParseError``
other 4xx       ``MarketdataHttpError``
==============  ==========================================================
"""

from datetime import datetime

from httpx import Request, Response
from pytz import timezone

SUPPORT_CONTEXT_FIELDS = (
    "request_id",
    "request_url",
    "status_code",
    "timestamp",
    "message",
    "exception_type",
)

NOT_AVAILABLE = "N/A"


class BaseMarketdataException(Exception):
    """Root of the SDK's exception hierarchy.

    Failures that never reached the API (validation, the rate-limit pre-flight,
    status data) carry ``N/A`` / ``0`` for the request fields;
    ``MarketdataHttpError`` fills them from the request and response.
    """

    def __init__(
        self,
        message: str,
        timestamp: datetime | str | None = None,
        *,
        request_id: str = NOT_AVAILABLE,
        request_url: str = NOT_AVAILABLE,
        status_code: int = 0,
    ):
        super().__init__(message)
        self.message = message
        self.timestamp = self._coerce_timestamp(timestamp)
        self.request_id = request_id
        self.request_url = request_url
        self.status_code = status_code

    @classmethod
    def format_timestamp(cls, timestamp: datetime) -> str:
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _coerce_timestamp(cls, timestamp: datetime | str | None) -> str:
        if timestamp is None:
            return cls.format_timestamp(datetime.now(timezone("US/Eastern")))
        if isinstance(timestamp, datetime):
            return cls.format_timestamp(timestamp)
        return timestamp

    @property
    def exception_type(self) -> str:
        return self.__class__.__name__

    @property
    def support_context(self) -> dict:
        """The §6.2 fields, in the order support expects them."""
        return {field: getattr(self, field) for field in SUPPORT_CONTEXT_FIELDS}

    @property
    def support_info(self) -> str:
        """The §6.3 block a user can paste into a support ticket."""
        width = max(len(field) for field in SUPPORT_CONTEXT_FIELDS) + 1
        lines = ["--- MARKET DATA SUPPORT INFO ---"]
        for field, value in self.support_context.items():
            lines.append(f"{field + ':':<{width}} {value}")
        lines.append("--------------------------------")
        return "\n".join(lines)


def _request_id(response: Response | None) -> str:
    if response is None:
        return NOT_AVAILABLE
    return response.headers.get("cf-ray", NOT_AVAILABLE)


class MarketdataHttpError(BaseMarketdataException):
    """A failure with an HTTP request behind it.

    Raised directly only for statuses the taxonomy below does not name;
    ``request`` and ``response`` stay available for callers that need the
    headers (``response`` is ``None`` when the request never got an answer).
    """

    def __init__(
        self,
        message: str,
        request: Request,
        response: Response | None = None,
        timestamp: datetime | str | None = None,
    ):
        super().__init__(
            message,
            timestamp,
            request_id=_request_id(response),
            request_url=str(request.url) or NOT_AVAILABLE,
            status_code=response.status_code if response is not None else 0,
        )
        self.request = request
        self.response = response


class BadRequestError(MarketdataHttpError):
    """400: the API rejected the parameters. Not retried."""


class AuthenticationError(MarketdataHttpError):
    """401: missing or invalid token. Fails immediately, never retried."""


class ForbiddenError(MarketdataHttpError):
    """403: the token is valid but not allowed (plan or IP restriction)."""


class NotFoundError(MarketdataHttpError):
    """404 with an ``errmsg``: the question itself was invalid.

    A 404 without ``errmsg`` is an empty answer to a valid question; resource
    methods return an empty result for it instead of raising.
    """


class ServerError(MarketdataHttpError):
    """5xx. A plain 500 is terminal; 501 and above are retried."""


class NetworkError(MarketdataHttpError):
    """Connection failure or timeout: the request got no answer. Retried."""


class ParseError(MarketdataHttpError):
    """The API answered, but the body could not be decoded."""


class RateLimitError(BaseMarketdataException):
    """API credits exhausted.

    Raised by the pre-flight check before a request goes out (no HTTP context)
    and for a 429 answer from the API (with the response and, when the API sent
    one, ``retry_after`` in seconds). Never retried.
    """

    def __init__(
        self,
        message: str,
        timestamp: datetime | str | None = None,
        *,
        response: Response | None = None,
        retry_after: float | None = None,
    ):
        request = response.request if response is not None else None
        super().__init__(
            message,
            timestamp,
            request_id=_request_id(response),
            request_url=str(request.url) if request is not None else NOT_AVAILABLE,
            status_code=response.status_code if response is not None else 0,
        )
        self.response = response
        self.retry_after = retry_after


class KeywordOnlyArgumentError(BaseMarketdataException):
    pass


class InvalidStatusDataError(BaseMarketdataException):
    pass


class MinMaxValidationError(BaseMarketdataException):
    pass


class MinMaxValueValidationError(MinMaxValidationError):
    pass


class MinMaxDateValidationError(MinMaxValidationError):
    pass
