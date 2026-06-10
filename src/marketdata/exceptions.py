"""Exceptions for the MarketData Python SDK"""

from datetime import datetime

from httpx import Request, Response
from pytz import timezone


class BaseMarketdataException(Exception):

    def __init__(self, message: str, timestamp: datetime | None = None):
        super().__init__(message)
        self.message = message
        self.timestamp = timestamp or self.format_timestamp(
            datetime.now(timezone("US/Eastern"))
        )

    @classmethod
    def format_timestamp(cls, timestamp: datetime):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def support_context(self) -> dict:
        return dict(
            timestamp=self.timestamp,
            message=self.message,
            exception_type=self.__class__.__name__,
        )

    @classmethod
    def from_exception(cls, exception: Exception):
        timestamp = cls.format_timestamp(datetime.now(timezone("US/Eastern")))
        message = str(exception)
        return cls(message, timestamp)


class MarketdataHttpError(BaseMarketdataException):
    def __init__(
        self,
        message: str,
        request: Request,
        response: Response | None = None,
        timestamp: datetime | None = None,
    ):
        super().__init__(message, timestamp)
        self.request = request
        self.response = response

    @property
    def request_id(self) -> str:
        if not self.response:
            return "N/A"
        return self.response.headers.get("cf-ray", "N/A")

    @property
    def request_url(self) -> str:
        return str(self.request.url) or "N/A"

    @property
    def status_code(self) -> int:
        if not self.response:
            return 0
        return self.response.status_code or 0

    @property
    def support_context(self) -> dict:
        return dict(
            request_id=self.request_id,
            request_url=self.request_url,
            status_code=self.status_code,
            timestamp=self.timestamp,
            message=self.message,
            exception_type=self.__class__.__name__,
        )


class BadStatusCodeError(MarketdataHttpError):
    pass


class RequestError(MarketdataHttpError):
    pass


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
