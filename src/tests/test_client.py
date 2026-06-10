import datetime
import os
from logging import Logger
from unittest.mock import MagicMock, patch

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
from marketdata.sdk_error import MarketDataClientErrorResult
from marketdata.settings import MarketDataSettings, settings
from marketdata.types import UserRateLimits
from marketdata.utils import format_duration_log


def test_user_rate_limits_str():
    user_rate_limits = UserRateLimits(
        requests_limit=100,
        requests_remaining=50,
        requests_reset=1734567890,
        requests_consumed=50,
    )
    assert isinstance(str(user_rate_limits), str)


def test_client_user_agent(client):
    assert client._get_user_agent() == f"marketdata-sdk-py/{client.library_version}"


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


def test_client_make_request_retry(client, respx_mock, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    from marketdata.api_status import API_STATUS_DATA

    monkeypatch.setattr(
        API_STATUS_DATA,
        "_trigger_async_refresh",
        lambda c: API_STATUS_DATA.refresh(c),
    )

    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={},
        status_code=502,
    )

    result = client.stocks.prices(symbols="AAPL")
    assert isinstance(result, MarketDataClientErrorResult)

    prices_calls = [
        c for c in respx_mock.calls if c.request.url.path == "/v1/stocks/prices/"
    ]
    status_calls = [
        c for c in respx_mock.calls if c.request.url.path == "/status/"
    ]
    assert len(prices_calls) == 4
    assert len(status_calls) == 1
    assert respx_mock.calls.call_count == 6


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
    assert client._get_user_agent() == f"marketdata-sdk-py/{client.library_version}"


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
    expected_utc = datetime.datetime(
        2024, 12, 19, 0, 24, 50, tzinfo=datetime.timezone.utc
    )
    expected_eastern = expected_utc.astimezone(pytz.timezone("US/Eastern"))
    assert (
        client.rate_limits.requests_reset.astimezone(pytz.timezone("US/Eastern"))
        == expected_eastern
    )
    assert client.rate_limits.requests_consumed == 1
    # fromtimestamp with US/Eastern converts UTC timestamp to US/Eastern local time
    expected_from_ts = datetime.datetime.fromtimestamp(
        1734567890, tz=pytz.timezone("US/Eastern")
    )
    assert (
        client.rate_limits.requests_reset.astimezone(pytz.timezone("US/Eastern"))
        == expected_from_ts
    )


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
    expected = datetime.datetime.fromtimestamp(
        1734567890, tz=pytz.timezone("US/Eastern")
    )
    assert (
        user_rate_limits.requests_reset.astimezone(pytz.timezone("US/Eastern"))
        == expected
    )
    assert user_rate_limits.requests_consumed == 1


def test_client_pre_and_post_request_logs(client, respx_mock):
    headers = {
        "cf-ray": "1234567890",
        "x-api-ratelimit-limit": "60",
        "x-api-ratelimit-remaining": "59",
        "x-api-ratelimit-reset": "1734567890",
        "x-api-ratelimit-consumed": "1",
    }
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={}, status_code=200, headers=headers
    )
    client = MarketDataClient(token="test")

    with patch.object(client.logger, "log") as mock_logger_info:
        with patch(
            "marketdata.client.format_duration_log", return_variable="000ms"
        ) as mock_format:
            mock_format.return_value = "000ms"
            client.stocks.prices(symbols="AAPL")
            last_request = respx_mock.calls.last
            mock_logger_info.call_args_list[0].assert_called_with(
                f"GET 200 000ms 1234567890 {last_request.request.url}"
            )


def test_client_max_retries_default(client):
    assert client.max_retries == 3


def test_client_max_retries_custom():
    with patch.object(MarketDataClient, "_setup_rate_limits"):
        c = MarketDataClient(token="test", max_retries=5)
    assert c.max_retries == 5


def test_client_max_retries_zero():
    with patch.object(MarketDataClient, "_setup_rate_limits"):
        c = MarketDataClient(token="test", max_retries=0)
    assert c.max_retries == 0


def test_client_max_retries_negative_raises():
    with pytest.raises(ValueError):
        MarketDataClient(token="test", max_retries=-1)


def test_client_max_retries_zero_no_retry(respx_mock, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    headers = {
        "x-api-ratelimit-limit": "100",
        "x-api-ratelimit-remaining": "99",
        "x-api-ratelimit-reset": "60",
        "x-api-ratelimit-consumed": "1",
    }
    respx_mock.get("https://api.marketdata.app/user/").respond(
        json={}, headers=headers, status_code=200
    )
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={}, status_code=502
    )

    c = MarketDataClient(token="test", max_retries=0)
    setattr(
        c,
        "_extract_rate_limits",
        lambda x: UserRateLimits(
            requests_limit=100,
            requests_remaining=99,
            requests_reset=60,
            requests_consumed=1,
        ),
    )

    result = c.stocks.prices(symbols="AAPL")
    assert isinstance(result, MarketDataClientErrorResult)
    assert respx_mock.calls.call_count == 2


def test_client_max_retries_one(respx_mock, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    headers = {
        "x-api-ratelimit-limit": "100",
        "x-api-ratelimit-remaining": "99",
        "x-api-ratelimit-reset": "60",
        "x-api-ratelimit-consumed": "1",
    }
    respx_mock.get("https://api.marketdata.app/user/").respond(
        json={}, headers=headers, status_code=200
    )
    import time as _time

    _now = _time.time()
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json={
            "service": ["/v1/stocks/bulkquotes/"],
            "status": ["online"],
            "online": [True],
            "uptimePct30d": [100],
            "uptimePct90d": [100],
            "updated": [_now],
        },
        headers=headers,
        status_code=200,
    )
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={}, status_code=502
    )

    c = MarketDataClient(token="test", max_retries=1)
    setattr(
        c,
        "_extract_rate_limits",
        lambda x: UserRateLimits(
            requests_limit=100,
            requests_remaining=99,
            requests_reset=60,
            requests_consumed=1,
        ),
    )

    result = c.stocks.prices(symbols="AAPL")
    assert isinstance(result, MarketDataClientErrorResult)
    prices_calls = [c for c in respx_mock.calls if c.request.url.path == "/v1/stocks/prices/"]
    assert len(prices_calls) == 2


def test_settings_extra_env_vars():
    with patch.dict(
        os.environ, {"RANDOM_VAR_FOR_TESTING": "123", "MARKETDATA_TOKEN": "test_token"}
    ):
        settings = MarketDataSettings()
        assert settings.marketdata_token == "test_token"


def test_default_logging_level_is_warning(monkeypatch):
    """Issue #25: the SDK must default to WARNING so importing it does not
    flood the user's terminal with INFO output.
    """
    monkeypatch.delenv("MARKETDATA_LOGGING_LEVEL", raising=False)
    fresh_settings = MarketDataSettings()
    assert fresh_settings.marketdata_logging_level == "WARNING"


def test_client_init_base_url_and_api_version_logged_at_debug(respx_mock):
    """Issue #25: `Base URL` and `API Version` must be logged at DEBUG rather
    than INFO so that the default INFO output stays quiet.
    """
    headers = {
        "x-api-ratelimit-limit": "100",
        "x-api-ratelimit-remaining": "99",
        "x-api-ratelimit-reset": "60",
        "x-api-ratelimit-consumed": "1",
    }
    respx_mock.get("https://api.marketdata.app/user/").respond(
        json={}, headers=headers, status_code=200
    )

    logger = MagicMock(spec=Logger)
    MarketDataClient(token="test", logger=logger)

    info_messages = [call.args[0] for call in logger.info.call_args_list]
    debug_messages = [call.args[0] for call in logger.debug.call_args_list]

    # Sanity: the constructor still emits the top-level "Initializing" line at
    # INFO, so the mock is wired correctly.
    assert any("Initializing" in m for m in info_messages)

    # The noisy details must not be at INFO anymore.
    assert not any("Base URL" in m for m in info_messages)
    assert not any("API Version" in m for m in info_messages)

    # They must still be available, just at DEBUG.
    assert any("Base URL" in m for m in debug_messages)
    assert any("API Version" in m for m in debug_messages)
