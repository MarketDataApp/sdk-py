from datetime import datetime

from httpx import Request, Response
from pytz import timezone

from marketdata.exceptions import (
    BadStatusCodeError,
    InvalidStatusDataError,
    KeywordOnlyArgumentError,
    MinMaxDateValidationError,
    RateLimitError,
    RequestError,
)
from marketdata.resources.base import BaseResource
from marketdata.sdk_error import (
    BaseMarketdataException,
    MarketDataClientErrorResult,
    handle_exceptions,
)


class DummyResource(BaseResource):
    @handle_exceptions
    def sample_function(self, exception_to_raise: Exception | None = None) -> None:
        if exception_to_raise:
            raise exception_to_raise
        return None


def test_client_error_result_str():
    timestamp = datetime.now(timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M:%S")
    error = BaseMarketdataException("test exception", timestamp=timestamp)
    result = MarketDataClientErrorResult(error=error)
    assert isinstance(result, MarketDataClientErrorResult)
    expected_msg = f"MarketDataClientErrorResult(\n\ttimestamp={timestamp}\n\tmessage=test exception\n\texception_type=BaseMarketdataException\n)"
    assert str(result) == expected_msg


def test_handle_exceptions(client):
    resource = DummyResource(client=client)
    result = resource.sample_function(exception_to_raise=Exception("test exception"))
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "test exception"


def test_handle_exceptions_no_exception(client):
    resource = DummyResource(client=client)
    result = resource.sample_function()
    assert result is None


def test_handle_exceptions_rate_limit_error(client):
    resource = DummyResource(client=client)
    result = resource.sample_function(
        exception_to_raise=RateLimitError("test exception")
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "test exception"


def test_handle_exceptions_request_error(client):
    resource = DummyResource(client=client)
    result = resource.sample_function(
        exception_to_raise=RequestError(
            "test exception",
            request=Request(method="GET", url="https://example.com"),
            response=Response(status_code=429),
        )
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "test exception"


def test_handle_exceptions_bad_status_code_error(client):
    resource = DummyResource(client=client)
    result = resource.sample_function(
        exception_to_raise=BadStatusCodeError(
            "test exception",
            request=Request(method="GET", url="https://example.com"),
            response=Response(status_code=501),
        )
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.message == "test exception"


def test_handle_exceptions_invalid_status_data_error(client):
    resource = DummyResource(client=client)
    result = resource.sample_function(
        exception_to_raise=InvalidStatusDataError("test exception")
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.message == "test exception"


def test_handle_exceptions_keyword_only_argument_error(client):
    resource = DummyResource(client=client)
    result = resource.sample_function(
        exception_to_raise=KeywordOnlyArgumentError("test exception")
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "test exception"


def test_handle_exceptions_min_max_validation_error(client):
    resource = DummyResource(client=client)
    result = resource.sample_function(
        exception_to_raise=MinMaxDateValidationError("test exception")
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "test exception"
