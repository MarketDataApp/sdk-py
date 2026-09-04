"""The exception surface (#20): resource methods raise, and every exception
carries the support context of SDK requirements section 6.2 plus the
support_info block of section 6.3."""

from datetime import datetime

import pytest
from httpx import Request, Response
from pytz import timezone

import marketdata
from marketdata.exceptions import (
    SUPPORT_CONTEXT_FIELDS,
    BadRequestError,
    BaseMarketdataException,
    InvalidStatusDataError,
    KeywordOnlyArgumentError,
    MarketdataHttpError,
    MinMaxDateValidationError,
    MinMaxValidationError,
    MinMaxValueValidationError,
    RateLimitError,
    ServerError,
)
from marketdata.input_types.base import OutputFormat

REQUEST = Request(method="GET", url="https://api.marketdata.app/v1/stocks/quotes/")


def test_base_exception_carries_the_full_support_context():
    error = BaseMarketdataException("test exception", timestamp="2022-01-01 00:00:00")

    assert str(error) == "test exception"
    assert error.support_context == {
        "request_id": "N/A",
        "request_url": "N/A",
        "status_code": 0,
        "timestamp": "2022-01-01 00:00:00",
        "message": "test exception",
        "exception_type": "BaseMarketdataException",
    }
    assert list(error.support_context) == list(SUPPORT_CONTEXT_FIELDS)


def test_base_exception_timestamp_defaults_to_now_in_eastern_time():
    before = datetime.now(timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M")

    error = RateLimitError("Rate limit exceeded")

    assert error.timestamp.startswith(before[:13])
    assert len(error.timestamp) == len("2022-01-01 00:00:00")


def test_base_exception_accepts_a_datetime_timestamp():
    stamp = datetime(2022, 1, 1, 12, 30, 45, tzinfo=timezone("US/Eastern"))

    error = InvalidStatusDataError("bad data", timestamp=stamp)

    assert error.timestamp == "2022-01-01 12:30:45"


def test_support_info_matches_the_spec_layout():
    error = RateLimitError(
        "Rate limit exceeded",
        response=Response(
            429, headers={"cf-ray": "8a1b2c3d4e5f6g7h-SJC"}, request=REQUEST
        ),
        timestamp="2025-02-21 12:00:00",
    )

    assert error.support_info == "\n".join(
        [
            "--- MARKET DATA SUPPORT INFO ---",
            "request_id:     8a1b2c3d4e5f6g7h-SJC",
            "request_url:    https://api.marketdata.app/v1/stocks/quotes/",
            "status_code:    429",
            "timestamp:      2025-02-21 12:00:00",
            "message:        Rate limit exceeded",
            "exception_type: RateLimitError",
            "--------------------------------",
        ]
    )


def test_http_error_without_a_response_reports_not_available():
    error = MarketdataHttpError("connection dropped", request=REQUEST, response=None)

    assert error.request_id == "N/A"
    assert error.request_url == "https://api.marketdata.app/v1/stocks/quotes/"
    assert error.status_code == 0
    assert error.request is REQUEST
    assert error.response is None
    assert "status_code:    0" in error.support_info


def test_http_error_keeps_request_and_response():
    response = Response(502, request=REQUEST)

    error = ServerError(
        "Request failed with: gateway", request=REQUEST, response=response
    )

    assert error.response is response
    assert error.status_code == 502
    assert error.request_id == "N/A"


@pytest.mark.parametrize(
    "exception_class",
    [
        RateLimitError,
        KeywordOnlyArgumentError,
        InvalidStatusDataError,
        MinMaxValidationError,
        MinMaxValueValidationError,
        MinMaxDateValidationError,
    ],
)
def test_every_non_http_exception_has_support_context(exception_class):
    error = exception_class("test exception")

    assert isinstance(error, BaseMarketdataException)
    assert set(error.support_context) == set(SUPPORT_CONTEXT_FIELDS)
    assert error.exception_type == exception_class.__name__
    assert error.support_info.splitlines()[-2] == (
        f"exception_type: {exception_class.__name__}"
    )


def test_every_exception_is_exported_from_the_package_root():
    for name in (
        "BaseMarketdataException",
        "MarketdataHttpError",
        "BadRequestError",
        "AuthenticationError",
        "ForbiddenError",
        "NotFoundError",
        "ServerError",
        "NetworkError",
        "ParseError",
        "RateLimitError",
        "KeywordOnlyArgumentError",
        "InvalidStatusDataError",
        "MinMaxValidationError",
        "MinMaxValueValidationError",
        "MinMaxDateValidationError",
    ):
        assert name in marketdata.__all__
        assert getattr(marketdata, name) is getattr(marketdata.exceptions, name)
    assert not hasattr(marketdata, "MarketDataClientErrorResult")


def test_resource_methods_raise_instead_of_returning_an_error_result(
    respx_mock, client, caplog
):
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={
            "s": "error",
            "errmsg": "Bad parameters, please check API documentation.",
        },
        status_code=400,
    )

    with pytest.raises(BadRequestError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)

    error = exc_info.value
    assert error.status_code == 400
    assert error.message == "Bad parameters, please check API documentation."
    assert error.request_url.startswith("https://api.marketdata.app/v1/stocks/prices/")
    assert "--- MARKET DATA SUPPORT INFO ---" in error.support_info
    # The terminal failure is logged once at ERROR (SDK requirements section 7).
    assert any(
        record.levelname == "ERROR" and "prices failed" in record.getMessage()
        for record in caplog.records
    )


def test_validation_errors_raise_before_any_request(respx_mock, client):
    import datetime as dt

    with pytest.raises(MinMaxDateValidationError):
        client.stocks.candles(
            "AAPL",
            from_date=dt.date(2024, 12, 31),
            to_date=dt.date(2024, 1, 1),
            output_format=OutputFormat.INTERNAL,
        )

    with pytest.raises(KeywordOnlyArgumentError):
        client.stocks.prices("AAPL", OutputFormat.INTERNAL)

    assert not [
        c for c in respx_mock.calls if c.request.url.path.startswith("/v1/stocks/")
    ]
