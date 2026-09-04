"""Exceptions for the MarketData Python SDK.

Every resource method raises on failure (SDK requirements §6.4). Every
exception carries the support context of §6.2 and renders it through
``support_info`` (§6.3), so a caller can paste one block into a support ticket.
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

    Non-HTTP failures (validation, rate-limit pre-flight, status data) carry
    ``N/A`` / ``0`` for the request fields; ``MarketdataHttpError`` fills them
    from the request and response.
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


class MarketdataHttpError(BaseMarketdataException):
    """A failure with an HTTP request behind it.

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
            request_id=(
                response.headers.get("cf-ray", NOT_AVAILABLE)
                if response is not None
                else NOT_AVAILABLE
            ),
            request_url=str(request.url) or NOT_AVAILABLE,
            status_code=response.status_code if response is not None else 0,
        )
        self.request = request
        self.response = response


class BadStatusCodeError(MarketdataHttpError):
    """A terminal HTTP status: not retried."""


class RequestError(MarketdataHttpError):
    """A retryable HTTP status (server errors above 500)."""


class RateLimitError(BaseMarketdataException):
    pass


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
