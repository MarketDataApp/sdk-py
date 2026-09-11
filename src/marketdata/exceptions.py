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
500             ``InternalError`` (the API failed; never retried)
501 to 599      ``ServerError`` (the API is unavailable; retried with backoff)
transport       ``NetworkError`` (retried unless the client caused it)
undecodable     ``ParseError`` (bad JSON or a body that does not match its
                Content-Encoding)
other 4xx       ``MarketdataHttpError``
==============  ==========================================================
"""

from datetime import datetime

from httpx import Request, Response
from pytz import timezone

from marketdata.internal_settings import HEADER_AUTHORIZED_IP

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
    """403: the token is valid but not allowed (plan or IP restriction).

    When the API blocks a call because it came from another address, it names
    the address the account is bound to in ``X-API-Authorized-IP``. That
    address is on ``authorized_ip`` and in the message (#44), because a caller
    who reads only the message would otherwise be told "access denied" with no
    way to know which address to allow. It is ``None`` for a 403 that is not
    an IP block.

    The body of that 403 carries more than the header does: the address that
    was blocked and a link to the troubleshooting guide. Both stay on
    ``response``, since the SDK reads the header the API asked the clients to
    move to (MarketData-App/api#202) rather than the body's field names.
    """

    def __init__(
        self,
        message: str,
        request: Request,
        response: Response | None = None,
        timestamp: datetime | str | None = None,
    ):
        header = (
            response.headers.get(HEADER_AUTHORIZED_IP) if response is not None else None
        )
        # A blank header is not an address: `''` would read as one to a
        # caller checking `if error.authorized_ip`.
        authorized_ip = header.strip() if header else None
        authorized_ip = authorized_ip or None
        if authorized_ip:
            sentence = f"This account is authorized for {authorized_ip}."
            # A 403 whose body carried no `errmsg` leaves the message empty or
            # the raw body; either way the sentence has to read on its own.
            message = f"{message.strip()} {sentence}".strip()
        super().__init__(message, request, response, timestamp)
        self.authorized_ip = authorized_ip


class NotFoundError(MarketdataHttpError):
    """404 with an ``errmsg``: the question itself was invalid.

    A 404 without ``errmsg`` is an empty answer to a valid question; resource
    methods return an empty result for it instead of raising.
    """


class InternalError(MarketdataHttpError):
    """500: the API itself failed on the request. Retrying will not help, so
    it is terminal. Not a ``ServerError``: catching one never catches the
    other."""


class ServerError(MarketdataHttpError):
    """501 to 599: the API is unavailable or a gateway answered for it. The
    request never ran, so it is retried with exponential backoff."""


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
