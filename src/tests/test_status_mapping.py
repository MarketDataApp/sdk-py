"""HTTP status to exception mapping (#62, SDK requirements sections 6.1 and
9.1): one class per failure, retries only where the spec allows them, and a
404 without errmsg is an empty result rather than an error."""

import pathlib
from unittest.mock import patch

import httpx
import pytest

from marketdata.api_error import should_retry
from marketdata.api_status import API_STATUS_DATA
from marketdata.exceptions import (
    AuthenticationError,
    BadRequestError,
    ForbiddenError,
    InternalError,
    MarketdataHttpError,
    NetworkError,
    NotFoundError,
    ParseError,
    RateLimitError,
    ServerError,
)
from marketdata.input_types.base import OutputFormat
from marketdata.output_types.options_expirations import OptionsExpirations
from marketdata.output_types.stocks_candles import StockCandle

PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"
EXPIRATIONS_URL = "https://api.marketdata.app/v1/options/expirations/AAPL/"
CANDLES_URL = "https://api.marketdata.app/v1/stocks/candles/H/AAPL/"
QUOTES_URL = "https://api.marketdata.app/v1/options/quotes/"
ERROR_BODY = {"s": "error", "errmsg": "Bad parameters, please check API documentation."}
NO_DATA = {"s": "no_data"}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)


@pytest.mark.parametrize(
    ("status", "exception_class"),
    [
        (400, BadRequestError),
        (401, AuthenticationError),
        (403, ForbiddenError),
        (404, NotFoundError),
        (429, RateLimitError),
        (500, InternalError),
        (502, ServerError),
        (418, MarketdataHttpError),
    ],
)
def test_status_maps_to_its_exception(respx_mock, client, status, exception_class):
    respx_mock.get(PRICES_URL).respond(json=ERROR_BODY, status_code=status)

    with pytest.raises(exception_class) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.status_code == status
    assert error.message == ERROR_BODY["errmsg"]
    assert error.request_url.startswith(PRICES_URL)
    assert error.exception_type == exception_class.__name__


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
def test_terminal_statuses_are_not_retried(respx_mock, client, status):
    route = respx_mock.get(PRICES_URL).respond(json=ERROR_BODY, status_code=status)

    with pytest.raises(MarketdataHttpError if status != 429 else RateLimitError):
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == 1


def test_server_errors_above_500_are_retried(respx_mock, client, monkeypatch):
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: API_STATUS_DATA.refresh(c)
    )
    route = respx_mock.get(PRICES_URL).respond(json={}, status_code=503)

    with pytest.raises(ServerError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert exc_info.value.status_code == 503
    assert route.call_count == client.max_retries + 1


def test_rate_limit_carries_retry_after_and_context(respx_mock, client):
    respx_mock.get(PRICES_URL).respond(
        json={"s": "error", "errmsg": "Rate limit exceeded"},
        status_code=429,
        headers={"Retry-After": "7", "cf-ray": "abc-EZE"},
    )

    with pytest.raises(RateLimitError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.retry_after == 7.0
    assert error.status_code == 429
    assert error.request_id == "abc-EZE"
    assert error.response.status_code == 429
    assert "status_code:    429" in error.support_info


def test_pre_flight_rate_limit_has_no_http_context():
    error = RateLimitError("Rate limit exceeded")

    assert error.retry_after is None
    assert error.response is None
    assert error.request_url == "N/A"
    assert error.status_code == 0


def test_network_errors_are_wrapped_and_retried(respx_mock, client, monkeypatch):
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: API_STATUS_DATA.refresh(c)
    )
    route = respx_mock.get(PRICES_URL).mock(side_effect=httpx.ConnectError("boom"))

    with pytest.raises(NetworkError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.message == "ConnectError: boom"
    assert error.request_url.startswith(PRICES_URL)
    assert error.response is None
    assert error.status_code == 0
    assert route.call_count == client.max_retries + 1


def test_should_retry_follows_the_spec():
    request = httpx.Request("GET", PRICES_URL)
    assert should_retry(NetworkError("timeout", request=request))
    assert should_retry(ServerError("x", request=request, response=httpx.Response(502)))
    assert not should_retry(
        InternalError("x", request=request, response=httpx.Response(500))
    )
    assert not should_retry(
        BadRequestError("x", request=request, response=httpx.Response(400))
    )
    assert not should_retry(RateLimitError("x"))
    assert not should_retry(ValueError("x"))


def test_a_500_and_a_gateway_error_are_different_exceptions():
    """A 500 means the API itself failed on the request; 501 and above mean
    the API was unavailable. Catching one must never catch the other."""
    assert not issubclass(InternalError, ServerError)
    assert not issubclass(ServerError, InternalError)
    assert issubclass(InternalError, MarketdataHttpError)


def test_undecodable_body_is_a_parse_error(respx_mock, client):
    route = respx_mock.get(PRICES_URL).respond(
        text="<html>nope</html>", status_code=200
    )

    with pytest.raises(ParseError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.status_code == 200
    assert "not valid JSON" in error.message
    assert "<html>nope</html>" in error.message
    assert route.call_count == 1


def test_status_refresh_survives_an_undecodable_body(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(
        text="not json", status_code=200
    )

    assert API_STATUS_DATA.refresh(client) is False


# ---------------------------------------------------------------- no data


def test_no_data_on_a_list_shaped_resource(respx_mock, client, tmp_path):
    respx_mock.get(PRICES_URL).respond(json=NO_DATA, status_code=404)

    assert client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL) == []
    assert client.stocks.prices("AAPL", output_format=OutputFormat.JSON) == NO_DATA

    csv_path = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename="empty.csv"
    )
    assert pathlib.Path(csv_path).read_bytes() == (
        b"symbol,mid,change,changepct,updated\r\n"
    )


def test_no_data_on_a_single_object_resource(respx_mock, client):
    respx_mock.get(EXPIRATIONS_URL).respond(json=NO_DATA, status_code=404)

    assert (
        client.options.expirations("AAPL", output_format=OutputFormat.INTERNAL) is None
    )
    assert (
        client.options.expirations("AAPL", output_format=OutputFormat.JSON) == NO_DATA
    )


def test_no_data_dataframe_has_the_model_columns_and_no_rows_pandas(respx_mock, client):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        respx_mock.get(EXPIRATIONS_URL).respond(json=NO_DATA, status_code=404)

        df = client.options.expirations("AAPL", output_format=OutputFormat.DATAFRAME)

        assert len(df) == 0
        assert set(df.columns) == {"expirations", "updated"}


def test_no_data_dataframe_has_the_model_columns_and_no_rows_polars(respx_mock, client):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["polars"]):
        respx_mock.get(PRICES_URL).respond(json=NO_DATA, status_code=404)

        df = client.stocks.prices("AAPL", output_format=OutputFormat.DATAFRAME)

        assert df.height == 0
        assert set(df.columns) == {"symbol", "mid", "change", "changepct", "updated"}


def test_no_data_candle_chunks_are_dropped_from_the_merge(
    load_json, respx_mock, client
):
    """A year-sized chunk with no data must not break the merge of the others."""
    mock_data = load_json("stocks_candles_response_200")
    respx_mock.get(CANDLES_URL).mock(
        side_effect=[
            httpx.Response(404, json=NO_DATA),
            httpx.Response(200, json=mock_data),
        ]
    )

    candles = client.stocks.candles(
        "AAPL",
        resolution="H",
        from_date="2023-01-01",
        to_date="2024-06-01",
        output_format=OutputFormat.INTERNAL,
    )

    assert len(candles) == len(mock_data["t"])
    assert all(isinstance(candle, StockCandle) for candle in candles)


def test_no_data_on_every_candle_chunk_is_an_empty_result(respx_mock, client):
    respx_mock.get(CANDLES_URL).respond(json=NO_DATA, status_code=404)

    candles = client.stocks.candles(
        "AAPL",
        resolution="H",
        from_date="2023-01-01",
        to_date="2024-06-01",
        output_format=OutputFormat.INTERNAL,
    )

    assert candles == []


def test_no_data_on_every_option_symbol_is_an_empty_result(respx_mock, client):
    respx_mock.get(url__regex=r".*/options/quotes/.*").respond(
        json=NO_DATA, status_code=404
    )

    quotes = client.options.quotes(
        ["AAPL250117C00150000", "AAPL250117P00150000"],
        output_format=OutputFormat.INTERNAL,
    )

    assert quotes is None


def test_no_data_on_one_option_symbol_keeps_the_others(load_json, respx_mock, client):
    mock_data = load_json("options_quotes_response_200")
    respx_mock.get(url__regex=r".*/options/quotes/AAPL250117C00150000/.*").respond(
        json=mock_data, status_code=200
    )
    respx_mock.get(url__regex=r".*/options/quotes/AAPL250117P00150000/.*").respond(
        json=NO_DATA, status_code=404
    )

    quotes = client.options.quotes(
        ["AAPL250117C00150000", "AAPL250117P00150000"],
        output_format=OutputFormat.INTERNAL,
    )

    assert len(quotes.optionSymbol) == len(mock_data["optionSymbol"])


def test_single_object_no_data_model_is_not_built(respx_mock, client):
    """Sanity check on the contract: the empty answer never reaches the model
    constructor, which would fail on the missing fields."""
    respx_mock.get(EXPIRATIONS_URL).respond(json=NO_DATA, status_code=404)

    result = client.options.expirations("AAPL", output_format=OutputFormat.INTERNAL)

    assert not isinstance(result, OptionsExpirations)


@pytest.mark.parametrize(
    ("call", "url_pattern", "empty"),
    [
        (lambda c: c.funds.candles("VFINX"), r".*/funds/candles/.*", []),
        (lambda c: c.markets.status(), r".*/markets/status/.*", []),
        (lambda c: c.stocks.news("AAPL"), r".*/stocks/news/.*", []),
        (lambda c: c.stocks.quotes("AAPL"), r".*/stocks/quotes/.*", []),
        (lambda c: c.options.chain("AAPL"), r".*/options/chain/.*", None),
        (lambda c: c.options.strikes("AAPL"), r".*/options/strikes/.*", None),
        (lambda c: c.stocks.earnings("AAPL"), r".*/stocks/earnings/.*", None),
        (
            lambda c: c.options.lookup("AAPL 28-00-2023 200.0 call"),
            r".*/options/lookup/.*",
            None,
        ),
    ],
)
def test_every_resource_renders_no_data_as_an_empty_result(
    respx_mock, client, call, url_pattern, empty
):
    respx_mock.get(url__regex=url_pattern).respond(json=NO_DATA, status_code=404)
    client.default_params.output_format = OutputFormat.INTERNAL

    assert call(client) == empty
