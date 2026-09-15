import datetime
import os
import time
from dataclasses import fields
from logging import DEBUG, ERROR, Logger
from unittest.mock import MagicMock, patch

import pytest
import pytz
from httpx import Request, Response

from marketdata.client import MarketDataClient
from marketdata.exceptions import BadRequestError, RateLimitError, ServerError
from marketdata.input_types.base import OutputFormat
from marketdata.internal_settings import NO_TOKEN_VALUE
from marketdata.settings import MarketDataSettings, settings
from marketdata.types import UserRateLimits
from src.tests.conftest import use_real_header_extraction

PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"


def test_user_rate_limits_str():
    user_rate_limits = UserRateLimits(
        credit_limit=100,
        credits_remaining=50,
        reset_time=1734567890,
        credits_consumed=50,
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

    with pytest.raises(ServerError):
        client.stocks.prices(symbols="AAPL")

    prices_calls = [
        c for c in respx_mock.calls if c.request.url.path == "/v1/stocks/prices/"
    ]
    status_calls = [c for c in respx_mock.calls if c.request.url.path == "/status/"]
    assert len(prices_calls) == 4
    assert len(status_calls) == 1
    assert respx_mock.calls.call_count == 6


def test_client_make_request_bad_status_not_retry(client, respx_mock):
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={},
        status_code=400,
    )

    with pytest.raises(BadRequestError):
        client.stocks.prices(symbols="AAPL")

    assert respx_mock.calls.call_count == 2

    # 1st request is for user rate limits
    assert respx_mock.calls[0].request.url.path == "/user/"

    # 2nd request is stocks.prices (and it fails with 400 status code and not retried)
    assert respx_mock.calls[1].request.url.path == "/v1/stocks/prices/"


def test_validate_user_universal_params__settings_default(monkeypatch):
    with (
        patch.object(MarketDataClient, "_make_request") as make_request_mock,
    ):
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
    assert client._rate_limits.state is not None


def test_check_rate_limits_does_nothing_when_it_is_not_asked_to_raise(client):
    """Demo mode and the `/user/` call at start-up go out unchecked, and the
    state is left exactly as it was."""
    state = _exhausted(time.time() + 3600)
    client._rate_limits.reset(state)

    client._check_rate_limits(raise_error=False)

    assert client._rate_limits.state is state


def test_client_no_token_not_check_rate_limits(respx_mock):
    client = MarketDataClient(token=NO_TOKEN_VALUE)
    route = respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={},
        status_code=200,
    )

    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    # Demo mode skips the pre-flight rate-limit check (no /user/ call either),
    # so the request goes straight out.
    assert route.called
    assert not [c for c in respx_mock.calls if c.request.url.path == "/user/"]


def _exhausted(reset_time) -> UserRateLimits:
    return UserRateLimits(
        credit_limit=100,
        credits_remaining=0,
        reset_time=reset_time,
        credits_consumed=100,
    )


def test_unknown_credits_do_not_refuse_a_request(respx_mock, client):
    """Issue #42: the tracker is fed by answers and the check runs before the
    request, so refusing on an unknown state made it unknowable forever and
    the client stayed bricked until it was built again."""
    client._rate_limits.reset()
    route = respx_mock.get(PRICES_URL).respond(json={"s": "ok"}, status_code=200)

    client._check_rate_limits(raise_error=True)
    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == 1


def test_an_answer_with_no_credit_headers_leaves_the_client_usable(respx_mock, client):
    """The same state, reached the way it happens in the wild: an answer that
    carries no `x-api-ratelimit-*` headers at all."""
    use_real_header_extraction(client)
    client._rate_limits.reset()
    client._rate_limits.reset()
    route = respx_mock.get(PRICES_URL).respond(json={"s": "ok"}, status_code=200)

    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == 2
    assert client._rate_limits.state is None


def test_exhausted_credits_refuse_the_request_until_the_window_resets(
    respx_mock, client
):
    state = _exhausted(time.time() + 3600)
    client._rate_limits.reset(state)
    route = respx_mock.get(PRICES_URL).respond(json={"s": "ok"}, status_code=200)

    with pytest.raises(RateLimitError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert not route.called, "the request must not go out"
    assert state.reset_time.isoformat() in error.message
    # About an hour: the round trip through `format_timestamp` and back moves
    # the value by a fraction of a microsecond in either direction.
    assert error.retry_after == pytest.approx(3600, abs=1)
    # A pre-flight refusal is the one RateLimitError with no HTTP context, which
    # is how a caller tells it from the API's own 429.
    assert error.response is None
    assert error.status_code == 0
    assert client._rate_limits.state is state


def test_a_refusal_writes_the_one_error_line_a_failure_gets(respx_mock, client, caplog):
    """`api_error_handler` writes one ERROR line per terminal failure (SDK
    requirements §7) and a pre-flight refusal passes through it like any other.
    Logging the refusal here too made alerting that counts ERROR records read
    one refusal as two."""
    client._rate_limits.reset(_exhausted(time.time() + 3600))
    respx_mock.get(PRICES_URL).respond(json={"s": "ok"}, status_code=200)

    with caplog.at_level(DEBUG, logger="marketdata"):
        with pytest.raises(RateLimitError):
            client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    errors = [record for record in caplog.records if record.levelno == ERROR]
    assert len(errors) == 1
    assert errors[0].getMessage().startswith("prices failed: No API credits left")


def test_exhausted_credits_of_a_window_that_reset_are_dropped(respx_mock, client):
    """Issue #42: `reset_time` was stored and never consulted, so one exhausted
    window refused every later request for the life of the client."""
    use_real_header_extraction(client)
    client._rate_limits.reset()
    stale = _exhausted(time.time() - 1)
    client._rate_limits.reset(stale)
    route = respx_mock.get(PRICES_URL).respond(json={"s": "ok"}, status_code=200)

    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == 1
    # Dropped rather than kept: this answer carries no credit headers, and a
    # stale "no credits left" must not come back to refuse the next request.
    assert client._rate_limits.state is None


def test_the_answer_that_gets_through_repopulates_the_tracker(respx_mock, client):
    use_real_header_extraction(client)
    client._rate_limits.reset()
    client._rate_limits.reset(_exhausted(time.time() - 1))
    respx_mock.get(PRICES_URL).respond(
        json={"s": "ok"},
        status_code=200,
        headers={
            "x-api-ratelimit-limit": "100",
            "x-api-ratelimit-remaining": "42",
            "x-api-ratelimit-reset": str(int(time.time()) + 60),
            "x-api-ratelimit-consumed": "58",
        },
    )

    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert client._rate_limits.state.credits_remaining == 42


def test_a_real_answer_that_reports_no_credits_left_refuses_the_next_call(
    respx_mock, client
):
    """The whole path with the headers the API really sends: an epoch reset in
    the future and a zero balance, read from the answer rather than seeded, and
    the refusal that follows on the next call. Every other test here builds the
    state by hand, which is how a reset time the SDK cannot read would go
    unnoticed."""
    use_real_header_extraction(client)
    client._rate_limits.reset()
    reset_at = int(time.time()) + 300
    route = respx_mock.get(PRICES_URL).respond(
        json={"s": "ok"},
        status_code=200,
        headers={
            "x-api-ratelimit-limit": "100",
            "x-api-ratelimit-remaining": "0",
            "x-api-ratelimit-reset": str(reset_at),
            "x-api-ratelimit-consumed": "100",
        },
    )

    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    with pytest.raises(RateLimitError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == 1, "the second request must not go out"
    assert exc_info.value.retry_after == pytest.approx(300, abs=2)


def test_a_naive_reset_time_is_read_in_the_zone_the_sdk_renders(
    respx_mock, client, monkeypatch
):
    """A `reset_time` that arrives without an offset is US/Eastern, the zone
    every timestamp in the SDK is rendered in. Reading it as UTC moved it by
    hours, which is a refusal that is early or late by that much.

    The wall time and the clock it is measured against are both fixed. Built
    from `now()`, the test read the machine's calendar: on the night the clocks
    go back, the hour it added landed on a wall time that happens twice, which
    is a value this state refuses outright.
    """
    eastern = pytz.timezone("US/Eastern")
    reset_wall_time = datetime.datetime(2030, 6, 15, 12, 0, 0)
    an_hour_before = eastern.localize(reset_wall_time).timestamp() - 3600
    monkeypatch.setattr("time.time", lambda: an_hour_before)
    client._rate_limits.reset(_exhausted(reset_wall_time))
    route = respx_mock.get(PRICES_URL).respond(json={"s": "ok"}, status_code=200)

    with pytest.raises(RateLimitError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert not route.called
    assert exc_info.value.retry_after == pytest.approx(3600, abs=2)


def test_a_reset_time_a_dst_change_repeats_is_refused_rather_than_moved(client):
    """01:30 on the night the clocks go back is two instants an hour apart, and
    the same wall time in the spring is none. Reading either as one moves the
    refusal by an hour without saying so, so the state refuses it and names
    what to pass instead."""
    for wall_time in (
        datetime.datetime(2026, 11, 1, 1, 30),  # happens twice
        datetime.datetime(2026, 3, 8, 2, 30),  # never happens
    ):
        with pytest.raises(ValueError, match="daylight-saving"):
            _exhausted(wall_time)

    aware = pytz.timezone("US/Eastern").localize(
        datetime.datetime(2026, 11, 1, 1, 30), is_dst=True
    )
    assert _exhausted(aware).reset_time == aware


def test_a_reset_time_the_client_cannot_read_lets_the_request_through(
    respx_mock, client
):
    """`60` in the reset header (the shape the SDK's own fixtures use) parses
    as a date in 1900. That is not a window that closed, it is a value this
    client cannot read: the request goes out, and the state is kept rather
    than dropped, since only its reset time is unreadable."""
    state = _exhausted(60)
    client._rate_limits.reset(state)

    # Before the request, so the kept state is the check's doing. Asserted
    # after the answer, the `client` fixture's own credit headers are what
    # decide it: they describe a later window with a higher balance, which
    # the tracker rejects as a late answer whatever this check did.
    client._check_rate_limits(raise_error=True)
    assert client._rate_limits.state is state

    route = respx_mock.get(PRICES_URL).respond(json={"s": "ok"}, status_code=200)
    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == 1


def test_a_429_leaves_the_pre_flight_speaking_for_the_next_call(respx_mock, client):
    """The API's `Retry-After` is what it asked for on that request; the
    pre-flight number that follows is the SDK's own, the time until the credit
    window resets. Both are seconds to wait, and they need not agree."""
    use_real_header_extraction(client)
    client._rate_limits.reset()
    route = respx_mock.get(PRICES_URL).respond(
        json={"s": "error", "errmsg": "Rate limit exceeded"},
        status_code=429,
        headers={
            "Retry-After": "30",
            "x-api-ratelimit-limit": "100",
            "x-api-ratelimit-remaining": "0",
            "x-api-ratelimit-reset": str(int(time.time()) + 300),
            "x-api-ratelimit-consumed": "100",
        },
    )

    with pytest.raises(RateLimitError) as from_the_api:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    with pytest.raises(RateLimitError) as from_the_sdk:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == 1
    assert from_the_api.value.retry_after == 30.0
    assert from_the_api.value.response is not None
    assert from_the_sdk.value.retry_after == pytest.approx(300, abs=2)
    assert from_the_sdk.value.response is None


def test_a_429_still_raises_with_its_response(respx_mock, client):
    """The other RateLimitError: the API's own answer, which keeps the HTTP
    context and the `Retry-After` it sent."""
    respx_mock.get(PRICES_URL).respond(
        json={"s": "error", "errmsg": "Rate limit exceeded"},
        status_code=429,
        headers={"Retry-After": "30"},
    )

    with pytest.raises(RateLimitError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.response is not None
    assert error.status_code == 429
    assert error.retry_after == 30.0


def test_client_raise_for_status_fails(client):
    request = Request(method="GET", url="https://api.marketdata.app/v1/stocks/prices/")
    response = Response(status_code=501, request=request)
    with pytest.raises(ServerError):
        client._raise_for_status(response)


def test_client_raise_for_status_passes(client):
    request = Request(method="GET", url="https://api.marketdata.app/v1/stocks/prices/")
    for status in (200, 203):
        client._raise_for_status(Response(status_code=status, request=request))


def test_client_raise_for_status_lets_the_no_data_answer_through(client):
    request = Request(method="GET", url="https://api.marketdata.app/v1/stocks/prices/")
    response = Response(status_code=404, json={"s": "no_data"}, request=request)
    client._raise_for_status(response)


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
    assert client._rate_limits.state.credit_limit == 60
    assert client._rate_limits.state.credits_remaining == 59
    # API returns UTC, convert to US/Eastern for comparison
    expected_utc = datetime.datetime(
        2024, 12, 19, 0, 24, 50, tzinfo=datetime.timezone.utc
    )
    expected_eastern = expected_utc.astimezone(pytz.timezone("US/Eastern"))
    assert (
        client._rate_limits.state.reset_time.astimezone(pytz.timezone("US/Eastern"))
        == expected_eastern
    )
    assert client._rate_limits.state.credits_consumed == 1
    # fromtimestamp with US/Eastern converts UTC timestamp to US/Eastern local time
    expected_from_ts = datetime.datetime.fromtimestamp(
        1734567890, tz=pytz.timezone("US/Eastern")
    )
    assert (
        client._rate_limits.state.reset_time.astimezone(pytz.timezone("US/Eastern"))
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
    assert user_rate_limits.credit_limit == 60
    assert user_rate_limits.credits_remaining == 59
    # API returns UTC, convert to US/Eastern for comparison
    expected = datetime.datetime.fromtimestamp(
        1734567890, tz=pytz.timezone("US/Eastern")
    )
    assert (
        user_rate_limits.reset_time.astimezone(pytz.timezone("US/Eastern")) == expected
    )
    assert user_rate_limits.credits_consumed == 1


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


@pytest.mark.parametrize("headers, reason", [({"cf-ray": ""}, "blank"), ({}, "absent")])
def test_the_response_log_line_says_n_a_when_there_is_no_request_id(
    client, respx_mock, headers, reason
):
    """The log line is read by a person looking for the id to quote. Without
    one it used to print the word `None`, or a gap where a blank header was,
    neither of which is an id (#114)."""
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={}, status_code=200, headers=headers
    )
    client = MarketDataClient(token="test")

    with patch.object(client.logger, "log") as logged:
        client.stocks.prices(symbols="AAPL")

    message = logged.call_args.args[1]
    assert " N/A " in message, reason
    assert "None" not in message


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
            credit_limit=100,
            credits_remaining=99,
            reset_time=60,
            credits_consumed=1,
        ),
    )

    with pytest.raises(ServerError):
        c.stocks.prices(symbols="AAPL")
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
            credit_limit=100,
            credits_remaining=99,
            reset_time=60,
            credits_consumed=1,
        ),
    )

    with pytest.raises(ServerError):
        c.stocks.prices(symbols="AAPL")
    prices_calls = [
        c for c in respx_mock.calls if c.request.url.path == "/v1/stocks/prices/"
    ]
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


def test_response_errmsg_is_bounded(client):
    # A hostile/malformed response body must not balloon exception messages
    request = Request("GET", "https://api.marketdata.app/v1/stocks/quotes/AAPL/")
    response = Response(502, text="x" * 100_000, request=request)

    with pytest.raises(ServerError) as exc_info:
        client._raise_for_status(response)
    assert len(str(exc_info.value)) < 1_000


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        # The JSON envelope: its errmsg, or the raw body when it is not text.
        (b'{"s": "error", "errmsg": "Bad symbol"}', ("Bad symbol", True)),
        (b'{"s": "error", "errmsg": ""}', ("", True)),
        (b'{"s": "error", "errmsg": null}', ('{"s": "error", "errmsg": null}', True)),
        (b'{"errmsg": ["a", "b"]}', ('{"errmsg": ["a", "b"]}', True)),
        (b'{"errmsg": {"k": "v"}}', ('{"errmsg": {"k": "v"}}', True)),
        (b'{"errmsg": 123}', ('{"errmsg": 123}', True)),
        # JSON without an errmsg, or not an object: not an error envelope.
        (b'{"s": "no_data"}', ('{"s": "no_data"}', False)),
        (b"[1, 2]", ("[1, 2]", False)),
        (b'"errmsg"', ('"errmsg"', False)),
        (b"42", ("42", False)),
        (b"null", ("null", False)),
        # The CSV envelope, with and without its header row (#91).
        (b's,errmsg\r\nerror,"Bad parameters"\r\n', ("Bad parameters", True)),
        (b"s,errmsg\r\nerror,\r\n", ("", True)),
        (b"no_data,Symbol not found.\r\n", ("Symbol not found.", True)),
        # Anything else is the raw body.
        (b"<html>error page</html>", ("<html>error page</html>", False)),
        (b"", ("", False)),
    ],
    ids=[
        "json-errmsg",
        "json-empty-errmsg",
        "json-null-errmsg",
        "json-list-errmsg",
        "json-object-errmsg",
        "json-number-errmsg",
        "json-no-errmsg",
        "json-list",
        "json-string",
        "json-number",
        "json-null",
        "csv-envelope",
        "csv-empty-errmsg",
        "csv-headerless-envelope",
        "html",
        "empty",
    ],
)
def test_error_message_reads_either_envelope_and_says_whether_it_found_one(
    body, expected
):
    """The message and the flag for each kind of body. The flag is what
    separates "invalid question" from "empty answer" on a 404 (#91)."""
    request = Request("GET", "https://api.marketdata.app/v1/stocks/quotes/AAPL/")
    response = Response(404, content=body, request=request)

    assert MarketDataClient._error_message(response) == expected


@pytest.mark.parametrize(
    "body",
    [
        b'{"s": "error", "errmsg": "' + b"x" * 1000 + b'"}',
        b"s,errmsg\r\nerror," + b"x" * 1000 + b"\r\n",
        b"x" * 1000,
    ],
    ids=["json-envelope", "csv-envelope", "raw-body"],
)
def test_error_message_is_bounded_on_every_path(body):
    """Each way out of `_error_message` bounds the message: a long errmsg
    cannot balloon exception messages and logs any more than a long body."""
    request = Request("GET", "https://api.marketdata.app/v1/stocks/quotes/AAPL/")
    response = Response(404, content=body, request=request)

    message, _ = MarketDataClient._error_message(response)

    assert message == "x" * 500 + "..."


def test_error_message_bounds_a_body_whose_errmsg_is_not_a_string():
    """The envelope carries an `errmsg` that is not text, so the message is the
    raw body. That way out bounds it too, and the 404 still counts as an error
    rather than the empty answer."""
    request = Request("GET", "https://api.marketdata.app/v1/stocks/quotes/AAPL/")
    body = b'{"s": "error", "errmsg": null, "pad": "' + b"x" * 1000 + b'"}'
    response = Response(404, content=body, request=request)

    message, has_errmsg = MarketDataClient._error_message(response)

    assert has_errmsg is True
    assert message.startswith('{"s": "error", "errmsg": null')
    assert len(message) == 503 and message.endswith("...")


def test_extract_rate_limits_missing_headers_returns_none(client, caplog):
    request = Request("GET", "https://api.marketdata.app/v1/stocks/quotes/AAPL/")
    response = Response(200, json={}, request=request)

    # Bypass the conftest instance-level patch to test the real method
    result = MarketDataClient._extract_rate_limits(client, response)
    assert result is None


def test_extract_rate_limits_garbage_headers_returns_none(client):
    request = Request("GET", "https://api.marketdata.app/v1/stocks/quotes/AAPL/")
    response = Response(
        200,
        json={},
        headers={
            "x-api-ratelimit-limit": "not-a-number",
            "x-api-ratelimit-remaining": "99",
            "x-api-ratelimit-reset": "60",
            "x-api-ratelimit-consumed": "1",
        },
        request=request,
    )

    result = MarketDataClient._extract_rate_limits(client, response)
    assert result is None


def test_make_request_keeps_rate_limits_on_malformed_response(client, respx_mock):
    # A malformed response (no rate-limit headers) must not crash the request
    # nor clobber previously known rate limits
    respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
        json={}, status_code=200
    )
    previous = client._rate_limits.state
    # Remove the conftest instance-level patch so the real extraction runs
    if "_extract_rate_limits" in client.__dict__:
        del client.__dict__["_extract_rate_limits"]

    response = client._make_request(method="GET", url="markets/status/")
    assert response.status_code == 200
    assert client._rate_limits.state == previous


RENAMED_FIELDS = (
    "requests_limit",
    "requests_remaining",
    "requests_reset",
    "requests_consumed",
)


def test_rate_limits_use_the_api_credits_nomenclature():
    """SDK requirements §8.1 (#48): the fields speak in API credits, as the
    product does, and the v1 ``requests_*`` names are gone without aliases."""
    rate_limits = UserRateLimits(
        credit_limit=100,
        credits_remaining=50,
        reset_time=1734567890,
        credits_consumed=50,
    )

    assert [field.name for field in fields(UserRateLimits)] == [
        "credit_limit",
        "credits_remaining",
        "reset_time",
        "credits_consumed",
    ]
    for old_name in RENAMED_FIELDS:
        assert not hasattr(rate_limits, old_name)
    assert str(rate_limits) == (
        f"Credits used 50/100, remaining: 50, reset at: {rate_limits.reset_time.isoformat()}"
    )
