import datetime
from unittest.mock import patch

import pytest
import pytz
from httpx import Request, Response

from marketdata.client import MarketDataClient
from marketdata.exceptions import (
    BadStatusCodeError,
    RateLimitError,
    RequestError,
)
from marketdata.input_types.base import OutputFormat
from marketdata.internal_settings import NO_TOKEN_VALUE
from marketdata.retry import get_retry_adapter
from marketdata.sdk_error import MarketDataClientErrorResult
from marketdata.settings import settings
from marketdata.types import UserRateLimits


def test_get_retry_adapter(client):
    retry_adapter = get_retry_adapter(
        attempts=3,
        backoff=0.5,
        exceptions=[],
        logger=client.logger,
    )
    assert retry_adapter is not None
    assert retry_adapter.stop.max_attempt_number == 3
    assert retry_adapter.wait.multiplier == 0.5
    assert retry_adapter.retry.exception_types == Exception
    assert retry_adapter.reraise == False
    assert retry_adapter.wait.min == 0.5
    assert retry_adapter.wait.max == 5


def test_user_rate_limits_str():
    user_rate_limits = UserRateLimits(
        requests_limit=100,
        requests_remaining=50,
        requests_reset=1734567890,
        requests_consumed=50,
    )
    assert isinstance(str(user_rate_limits), str)


def test_client_user_agent(client):
    assert client._get_user_agent() == f"marketdata-py-{client.library_version}"


def test_client_headers(client):
    assert client.headers == {
        "Authorization": f"Bearer {client.token}",
        "User-Agent": client.library_user_agent,
    }


def test_client_headers_no_token(respx_mock):
    client = MarketDataClient(token=NO_TOKEN_VALUE)
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={},
        status_code=200,
    )
    client.stocks.prices(symbols="AAPL")
    assert respx_mock.calls.call_count == 1
    assert client.headers == {
        "User-Agent": client.library_user_agent,
    }


def test_client_make_request_retry(client, respx_mock):
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={},
        status_code=502,
    )

    result = client.stocks.prices(symbols="AAPL")
    assert isinstance(result, MarketDataClientErrorResult)

    assert respx_mock.calls.call_count == 6

    # 1st request is for user rate limits
    assert respx_mock.calls[0].request.url.path == "/user/"

    # 2nd request is stocks.prices (and it fails with 502 status code)
    assert respx_mock.calls[1].request.url.path == "/v1/stocks/prices/"

    # 3rd request is API status check
    assert respx_mock.calls[2].request.url.path == "/status/"

    # 4th, 5th, 6th requests are retries
    assert respx_mock.calls[3].request.url.path == "/v1/stocks/prices/"
    assert respx_mock.calls[4].request.url.path == "/v1/stocks/prices/"
    assert respx_mock.calls[5].request.url.path == "/v1/stocks/prices/"


def test_client_make_request_bad_status_not_retry(client, respx_mock):
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={},
        status_code=400,
    )

    result = client.stocks.prices(symbols="AAPL")
    assert isinstance(result, MarketDataClientErrorResult)

    assert respx_mock.calls.call_count == 2

    # 1st request is for user rate limits
    assert respx_mock.calls[0].request.url.path == "/user/"

    # 2nd request is stocks.prices (and it fails with 400 status code and not retried)
    assert respx_mock.calls[1].request.url.path == "/v1/stocks/prices/"


def test_validate_user_universal_params__settings_default(monkeypatch):
    with (patch.object(MarketDataClient, "_make_request") as make_request_mock,):
        client = MarketDataClient(token="test")
        client.stocks.prices(symbols="AAPL")
        assert make_request_mock.called
        assert client.default_params.output_format == OutputFormat.DATAFRAME


def test_validate_user_universal_params__settings_json(load_json, respx_mock, client):
    mock_data = load_json("stocks_prices_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json=mock_data,
        status_code=200,
    )
    client.stocks.prices(symbols="AAPL", output_format=OutputFormat.JSON)
    assert "format=json" in str(respx_mock.calls.last.request.url.query)


def test_validate_user_universal_params__client_json(monkeypatch):
    with (
        patch.object(MarketDataClient, "_make_request") as make_request_mock,
        monkeypatch.context() as m,
    ):
        m.setenv("MARKETDATA_OUTPUT_FORMAT", OutputFormat.CSV.value)
        client = MarketDataClient(token="test")
        client.default_params.output_format = OutputFormat.JSON
        client.stocks.prices(symbols="AAPL")
        assert "format=json" in make_request_mock.call_args[1]["url"]


def test_validate_user_universal_params__function_json(monkeypatch):
    with (
        patch.object(MarketDataClient, "_make_request") as make_request_mock,
        monkeypatch.context() as m,
    ):
        m.setenv("MARKETDATA_OUTPUT_FORMAT", OutputFormat.CSV.value)
        client = MarketDataClient(token="test")
        client.default_params.output_format = OutputFormat.CSV
        client.stocks.prices(symbols="AAPL", output_format=OutputFormat.JSON)
        assert "format=json" in make_request_mock.call_args[1]["url"]


def test_client_get_user_agent(client):
    assert client._get_user_agent() == f"marketdata-py-{client.library_version}"


def test_client_get_headers(client):
    assert client._get_headers() == {
        "Authorization": f"Bearer {client.token}",
        "User-Agent": client.library_user_agent,
    }


def test_client_get_client(client):
    assert client.client.base_url == settings.marketdata_base_url
    assert client.client.headers["Authorization"] == f"Bearer {client.token}"
    assert client.client.headers["User-Agent"] == client.library_user_agent


def test_client_check_rate_limits(client):
    client._check_rate_limits(raise_error=True)
    assert client.rate_limits is not None


def test_client_no_token_not_check_rate_limits(respx_mock):
    client = MarketDataClient(token=NO_TOKEN_VALUE)
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={},
        status_code=200,
    )
    client.stocks.prices()


def test_client_check_rate_limits_no_rate_limits(client):
    client.rate_limits = None
    with pytest.raises(RateLimitError):
        client._check_rate_limits(raise_error=True)


def test_client_check_rate_limits_rate_limit_exceeded(client):
    client.rate_limits = UserRateLimits(
        requests_limit=100,
        requests_remaining=0,
        requests_reset=1734567890,
        requests_consumed=100,
    )
    with pytest.raises(RateLimitError):
        client._check_rate_limits(raise_error=True)


def test_client_raise_for_status_fails(client):
    request = Request(method="GET", url="https://api.marketdata.app/v1/stocks/prices/")
    response = Response(status_code=501, request=request)
    with pytest.raises(BadStatusCodeError):
        client._validate_response_status_code(
            response, retry_status_codes=[], raise_for_status=True
        )


def test_client_raise_for_status_passes(client):
    request = Request(method="GET", url="https://api.marketdata.app/v1/stocks/prices/")
    response = Response(status_code=200, request=request)
    client._validate_response_status_code(
        response, retry_status_codes=[], raise_for_status=True
    )


def test_raise_retry_status_codes_fails(client):
    request = Request(method="GET", url="https://api.marketdata.app/v1/stocks/prices/")
    response = Response(status_code=203, request=request)
    with pytest.raises(RequestError):
        client._validate_response_status_code(
            response, retry_status_codes=[203], raise_for_status=False
        )


def test_client_setup_rate_limits(respx_mock):

    respx_mock.get("https://api.marketdata.app/user/").respond(
        json={},
        status_code=200,
        headers={
            "x-api-ratelimit-limit": "60",
            "x-api-ratelimit-remaining": "59",
            "x-api-ratelimit-reset": "1734567890",
            "x-api-ratelimit-consumed": "1",
        },
    )

    client = MarketDataClient(token="test")
    client._setup_rate_limits()
    assert client.rate_limits.requests_limit == 60
    assert client.rate_limits.requests_remaining == 59
    # API returns UTC, convert to US/Eastern for comparison
    expected_utc = datetime.datetime(2024, 12, 19, 0, 24, 50, tzinfo=datetime.timezone.utc)
    expected_eastern = expected_utc.astimezone(pytz.timezone('US/Eastern'))
    assert client.rate_limits.requests_reset.astimezone(pytz.timezone('US/Eastern')) == expected_eastern
    assert client.rate_limits.requests_consumed == 1
    # fromtimestamp with US/Eastern converts UTC timestamp to US/Eastern local time
    expected_from_ts = datetime.datetime.fromtimestamp(1734567890, tz=pytz.timezone('US/Eastern'))
    assert client.rate_limits.requests_reset.astimezone(pytz.timezone('US/Eastern')) == expected_from_ts


def test_client_extract_rate_limits(respx_mock):
    headers = {
        "x-api-ratelimit-limit": "60",
        "x-api-ratelimit-remaining": "59",
        "x-api-ratelimit-reset": "1734567890",
        "x-api-ratelimit-consumed": "1",
    }
    respx_mock.get("https://api.marketdata.app/user/").respond(
        json={}, status_code=200, headers=headers
    )
    response = Response(status_code=200, headers=headers)
    client = MarketDataClient(token="test")
    user_rate_limits = client._extract_rate_limits(response)
    assert user_rate_limits.requests_limit == 60
    assert user_rate_limits.requests_remaining == 59
    # API returns UTC, convert to US/Eastern for comparison
    expected = datetime.datetime.fromtimestamp(1734567890, tz=pytz.timezone('US/Eastern'))
    assert user_rate_limits.requests_reset.astimezone(pytz.timezone('US/Eastern')) == expected
    assert user_rate_limits.requests_consumed == 1
