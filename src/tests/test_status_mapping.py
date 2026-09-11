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
QUOTES_URL_STOCKS = "https://api.marketdata.app/v1/stocks/quotes/"
ERROR_BODY = {"s": "error", "errmsg": "Bad parameters, please check API documentation."}
NO_DATA = {"s": "no_data"}
# The same envelope as the API renders it for `format=csv`: two lines, and the
# message quoted because it carries a comma (verified live, #91).
ERROR_CSV = 's,errmsg\r\nerror,"Bad parameters, please check API documentation."\r\n'
CSV_HEADERS = {"content-type": "text/csv; charset=utf-8"}


def error_response(status, envelope):
    """The API's error answer for `format=json` or for `format=csv`."""
    if envelope == "json":
        return httpx.Response(status, json=ERROR_BODY)
    return httpx.Response(status, text=ERROR_CSV, headers=CSV_HEADERS)


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
@pytest.mark.parametrize("envelope", ["json", "csv"])
def test_status_maps_to_its_exception(
    respx_mock, client, status, exception_class, envelope
):
    """The envelope the API answers with must not change the exception nor its
    message: the same error arrives as a JSON object or as a two-line CSV
    table depending on the format asked for, and the SDK reads both (#91)."""
    respx_mock.get(PRICES_URL).mock(return_value=error_response(status, envelope))

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
    caused_by_the_client = NetworkError("x", request=request)
    caused_by_the_client.__cause__ = httpx.UnsupportedProtocol("no scheme")
    assert not should_retry(caused_by_the_client)


@pytest.mark.parametrize(
    "transport_error",
    [
        httpx.UnsupportedProtocol("Request URL is missing an 'http://' protocol."),
        httpx.LocalProtocolError("Illegal header value b'Token abc\\n'"),
        httpx.ProxyError("403 Forbidden"),
    ],
)
def test_client_side_transport_errors_are_not_retried(
    respx_mock, client, transport_error
):
    """A base URL without a scheme, a malformed request or a proxy refusal fail
    the same way on every attempt: one NetworkError, one call, no backoff."""
    route = respx_mock.get(PRICES_URL).mock(side_effect=transport_error)

    with pytest.raises(NetworkError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.__cause__ is transport_error
    assert error.request_url.startswith(PRICES_URL)
    assert route.call_count == 1


def test_undecodable_content_encoding_is_a_parse_error(respx_mock, client):
    """A 200 whose body does not match its Content-Encoding (an intercepting
    proxy) is a ParseError with support context, not a raw httpx exception."""
    route = respx_mock.get(PRICES_URL).mock(side_effect=httpx.DecodingError("bad gzip"))

    with pytest.raises(ParseError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.message == "DecodingError: bad gzip"
    assert error.request_url.startswith(PRICES_URL)
    assert error.response is None
    assert route.call_count == 1


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


@pytest.mark.parametrize(
    ("output_format", "answer"),
    [
        (OutputFormat.JSON, {"json": {"s": "no_data", "errmsg": "Symbol not found."}}),
        (
            OutputFormat.CSV,
            {
                "text": "s,errmsg\r\nno_data,Symbol not found.\r\n",
                "headers": CSV_HEADERS,
            },
        ),
    ],
    ids=["json", "csv"],
)
def test_an_unknown_symbol_raises_on_every_output_format(
    respx_mock, client, output_format, answer, tmp_path
):
    """Issue #91: `stocks.quotes("ZZZZZZ")` is a 404 with a message, rendered as
    JSON or as the `s,errmsg` table depending on the format asked for (both
    verified live). The CSV one used to be read as the empty answer, so the same
    question raised `NotFoundError` as JSON and wrote a header-only file as
    CSV."""
    respx_mock.get(QUOTES_URL_STOCKS).respond(status_code=404, **answer)

    with pytest.raises(NotFoundError) as exc_info:
        client.stocks.quotes(
            "ZZZZZZ", output_format=output_format, filename=tmp_path / "out.csv"
        )

    assert exc_info.value.message == "Symbol not found."
    assert not (tmp_path / "out.csv").exists()


def test_an_unknown_symbol_raises_without_the_header_row(respx_mock, client, tmp_path):
    """Under `add_headers=False` the API drops the header row from the error
    table too and sends the values alone (verified live)."""
    respx_mock.get(QUOTES_URL_STOCKS).respond(
        text="no_data,Symbol not found.\r\n", status_code=404, headers=CSV_HEADERS
    )

    with pytest.raises(NotFoundError) as exc_info:
        client.stocks.quotes(
            "ZZZZZZ",
            output_format=OutputFormat.CSV,
            filename=tmp_path / "out.csv",
            add_headers=False,
        )

    assert exc_info.value.message == "Symbol not found."


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (404, "<html>the proxy ate it</html>"),
        (200, '0\r\n""\r\n'),
    ],
    ids=["404-that-is-not-the-error-table", "the-csv-no-data-placeholder"],
)
def test_a_404_without_a_message_is_still_the_empty_answer(
    respx_mock, client, tmp_path, status, body
):
    """The other half of the rule: only the error table makes a 404 an error.
    A 404 whose body is not one stays an empty result, and so does the CSV
    placeholder the API sends instead of a 404 (#89)."""
    respx_mock.get(PRICES_URL).respond(
        text=body, status_code=status, headers=CSV_HEADERS
    )

    path = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename=tmp_path / "empty.csv"
    )

    assert pathlib.Path(path).read_bytes() == b"symbol,mid,change,changepct,updated\r\n"


@pytest.mark.parametrize(
    ("body", "exception_class", "retried"),
    [
        ("oops\x00page", InternalError, False),
        ("<html>" + "a" * 200000, ServerError, True),
    ],
    ids=["a-nul-byte", "a-field-past-the-csv-reader-limit"],
)
def test_a_body_that_is_not_a_csv_keeps_its_exception_and_its_retries(
    respx_mock, client, body, exception_class, retried
):
    """Reading the CSV envelope must not change what a body the reader cannot
    parse does: `csv.Error` would replace the SDK's exception and, on a
    retryable status, `should_retry` would never see it."""
    status = 500 if exception_class is InternalError else 503
    route = respx_mock.get(PRICES_URL).respond(
        text=body, status_code=status, headers=CSV_HEADERS
    )

    with pytest.raises(exception_class):
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == (client.max_retries + 1 if retried else 1)


@pytest.mark.parametrize(
    "errmsg",
    [None, ["a", "b"], {"k": "v"}, 123],
    ids=["null", "list", "object", "number"],
)
def test_an_errmsg_that_is_not_text_still_raises_and_shows_the_body(
    respx_mock, client, errmsg
):
    """An `errmsg` of any type means the API said something, so a 404 carrying
    it is not the empty answer. The message shown is the raw body rather than
    Python's repr of the decoded value, which told the reader nothing (a null
    errmsg used to surface as the message "None")."""
    body = {"s": "error", "errmsg": errmsg}
    respx_mock.get(PRICES_URL).respond(json=body, status_code=404)

    with pytest.raises(NotFoundError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    message = exc_info.value.message
    assert message.startswith('{"s": "error"') or message.startswith('{"s":"error"')
    assert "errmsg" in message


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
        # `expirations` is the index, as in a populated frame (#84).
        assert df.index.name == "expirations"
        assert set(df.columns) == {"updated"}


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


@pytest.mark.parametrize(
    ("output_format", "expected"),
    [(OutputFormat.INTERNAL, []), (OutputFormat.JSON, NO_DATA)],
    ids=["internal", "json"],
)
def test_no_data_on_every_candle_chunk_is_an_empty_result(
    respx_mock, client, output_format, expected
):
    """`stocks.candles` is the one resource with no single response to echo
    when every chunk is empty, so the JSON output falls back to the canonical
    body rather than to one arbitrary chunk's."""
    respx_mock.get(CANDLES_URL).respond(json=NO_DATA, status_code=404)

    candles = client.stocks.candles(
        "AAPL",
        resolution="H",
        from_date="2023-01-01",
        to_date="2024-06-01",
        output_format=output_format,
    )

    assert candles == expected


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


@pytest.mark.parametrize("handler", ["pandas", "polars"])
def test_expirations_no_data_dataframe_has_the_shape_of_a_populated_one(
    load_json, respx_mock, client, handler
):
    """Issue #84: the empty frame carries the `expirations` index and the
    `updated` column, as a populated one does, so `pd.concat` across symbols
    keeps the index name and gains no stray column."""
    respx_mock.get(EXPIRATIONS_URL).respond(
        json=load_json("options_expirations_response_200"), status_code=200
    )
    respx_mock.get("https://api.marketdata.app/v1/options/expirations/ZZZZ/").respond(
        json=NO_DATA, status_code=404
    )

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", [handler]):
        populated = client.options.expirations(
            "AAPL", output_format=OutputFormat.DATAFRAME
        )
        empty = client.options.expirations("ZZZZ", output_format=OutputFormat.DATAFRAME)

    assert list(empty.columns) == list(populated.columns)
    if handler == "pandas":
        assert empty.index.name == populated.index.name == "expirations"
        assert list(populated.columns) == ["updated"]


# Every resource that renders an empty answer, with a populated fixture.
# `options.strikes` is left out on purpose: its columns are the expiration
# dates of the answer itself, so no empty frame can match a populated one; the
# resource is deprecated and goes away in #73.
RESOURCES = [
    pytest.param(call, url_pattern, fixture, id=fixture.replace("_response_200", ""))
    for call, url_pattern, fixture in [
        (
            lambda c: c.funds.candles("VFINX"),
            r".*/funds/candles/.*",
            "funds_candles_response_200",
        ),
        (
            lambda c: c.markets.status(),
            r".*/markets/status/.*",
            "markets_status_response_200",
        ),
        (
            lambda c: c.stocks.prices("AAPL"),
            r".*/stocks/prices/.*",
            "stocks_prices_response_200",
        ),
        (
            lambda c: c.stocks.quotes("AAPL"),
            r".*/stocks/quotes/.*",
            "stocks_quotes_response_200",
        ),
        (
            lambda c: c.stocks.candles("AAPL"),
            r".*/stocks/candles/.*",
            "stocks_candles_response_200",
        ),
        (
            lambda c: c.stocks.earnings("AAPL"),
            r".*/stocks/earnings/.*",
            "stocks_earnings_response_200",
        ),
        (
            lambda c: c.stocks.news("AAPL"),
            r".*/stocks/news/.*",
            "stocks_news_response_200",
        ),
        (
            lambda c: c.options.chain("AAPL"),
            r".*/options/chain/.*",
            "options_chain_response_200",
        ),
        (
            lambda c: c.options.expirations("AAPL"),
            r".*/options/expirations/.*",
            "options_expirations_response_200",
        ),
        (
            lambda c: c.options.lookup("AAPL 28-00-2023 200.0 call"),
            r".*/options/lookup/.*",
            "options_lookup_response_200",
        ),
        (
            lambda c: c.options.quotes("AAPL271217C00255000"),
            r".*/options/quotes/.*",
            "options_quotes_response_200",
        ),
    ]
]


@pytest.mark.parametrize(("call", "url_pattern", "fixture"), RESOURCES)
def test_every_resource_no_data_dataframe_has_the_shape_of_a_populated_one(
    load_json, respx_mock, client, call, url_pattern, fixture
):
    """Issue #84 for every resource: an empty DataFrame must be usable in
    place of a populated one (same index name, same columns), whatever the
    resource. `options.expirations` was the one that differed."""
    respx_mock.get(url__regex=url_pattern).mock(
        side_effect=[
            httpx.Response(200, json=load_json(fixture)),
            httpx.Response(404, json=NO_DATA),
        ]
    )
    client.default_params.output_format = OutputFormat.DATAFRAME

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        populated = call(client)
        empty = call(client)

    assert list(empty.index.names) == list(populated.index.names)
    assert list(empty.columns) == list(populated.columns)


@pytest.mark.parametrize(("call", "url_pattern", "fixture"), RESOURCES)
def test_every_resource_no_data_dataframe_honours_the_column_filter(
    load_json, respx_mock, client, call, url_pattern, fixture
):
    """Issue #87 for every resource: under `columns=` the API answers with the
    requested keys only, so the empty frame must carry the requested columns
    too, in request order. `stocks.candles` used to fail on the populated
    side as well (#90).

    The filter names two columns in the reverse of the model's order, and the
    mocked answer has the shape the API gives (checked live): the requested
    keys, in request order, and no status flag. With the model's own order the
    test could not tell request order from model order, which is how the
    fan-outs' merge got through in model order."""
    body = load_json(fixture)
    requested = [key for key in body if key != "s"][-2:][::-1]
    filtered = {key: body[key] for key in requested}
    respx_mock.get(url__regex=url_pattern).mock(
        side_effect=[
            httpx.Response(200, json=filtered),
            httpx.Response(404, json=NO_DATA),
        ]
    )
    client.default_params.output_format = OutputFormat.DATAFRAME
    client.default_params.columns = requested

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        populated = call(client)
        empty = call(client)

    assert list(empty.index.names) == list(populated.index.names)
    assert list(empty.columns) == list(populated.columns)
    names = [name for name in empty.index.names if name is not None]
    assert all(name in requested for name in [*names, *empty.columns])


def test_an_api_alias_column_filter_does_not_keep_the_no_data_shape(
    load_json, respx_mock, client
):
    """The documented limit of #87, pinned so it is a known behaviour rather
    than a surprise.

    The test above filters on the model's own field names, which always match.
    The API also resolves its own aliases (`open` for `o`, `price`, `date`),
    and those the SDK does not mirror: it cannot know which alias an endpoint
    accepts. So the API answers `columns=open` with the single column `o`
    while `model_columns` matches nothing and falls back to the full set, and
    the two frames stop having the same shape - the index included, which is
    what breaks a `pd.concat` across symbols.

    Mirroring the aliases is the fix; it needs a per-endpoint table from the
    API side first (`price` even depends on whether the market is open).
    """
    respx_mock.get(url__regex=r".*/stocks/candles/.*").mock(
        side_effect=[
            # What the API really answers for `columns=open`: the alias
            # resolved to `o`, and nothing else.
            httpx.Response(200, json={"s": "ok", "o": [1.0, 2.0]}),
            httpx.Response(404, json=NO_DATA),
        ]
    )
    client.default_params.output_format = OutputFormat.DATAFRAME
    client.default_params.columns = ["open"]

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        populated = client.stocks.candles("AAPL")
        empty = client.stocks.candles("AAPL")

    assert list(populated.columns) == ["o"]
    assert list(populated.index.names) == [None]
    # The empty frame keeps every model column and the `t` index: the shapes
    # differ, and that is the known gap.
    assert list(empty.columns) == ["o", "h", "l", "c", "v"]
    assert list(empty.index.names) == ["t"]


CSV_PLACEHOLDER = '0\r\n""\r\n'


@pytest.mark.parametrize(("call", "url_pattern", "fixture"), RESOURCES)
def test_every_resource_renders_the_csv_no_data_placeholder_as_a_header_only_file(
    respx_mock, client, call, url_pattern, fixture, tmp_path
):
    """Issue #89: in CSV format the empty answer arrives as a 200 whose body is
    a placeholder table (MarketData-App/api#422); it must be the same header-only
    file as a JSON 404 no_data, on every resource."""
    respx_mock.get(url__regex=url_pattern).respond(
        text=CSV_PLACEHOLDER,
        status_code=200,
        headers={"content-type": "text/csv; charset=utf-8"},
    )
    client.default_params.output_format = OutputFormat.CSV
    client.default_params.filename = tmp_path / "empty.csv"

    path = call(client)

    lines = pathlib.Path(path).read_bytes().split(b"\r\n")
    assert lines[1:] == [b""]
    assert lines[0] not in (b"", b"0")


@pytest.mark.parametrize(
    "body",
    [{}, {"content": b""}, {"text": "<html>404 Not Found</html>"}],
    ids=["json-no_data", "empty-body", "html-page"],
)
def test_a_no_data_404_is_empty_on_every_output_format_whatever_its_body(
    respx_mock, client, tmp_path, body
):
    """The output format must not decide whether a call raises (#91). A 404
    without `errmsg` is the empty answer by its status, so a body that does not
    decode -- a CDN or proxy answering the 404 with no JSON -- gets the
    canonical `{"s": "no_data"}` on the JSON path instead of a `ParseError`,
    which is what the other three formats already did."""
    kwargs = {"json": NO_DATA} if not body else body
    respx_mock.get(PRICES_URL).respond(status_code=404, **kwargs)

    assert client.stocks.prices("AAPL", output_format=OutputFormat.JSON) == NO_DATA
    assert client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL) == []
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        assert (
            len(client.stocks.prices("AAPL", output_format=OutputFormat.DATAFRAME)) == 0
        )
    path = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename=tmp_path / f"{len(kwargs)}.csv"
    )
    assert pathlib.Path(path).exists()


def test_no_data_csv_carries_the_requested_columns_in_request_order(
    respx_mock, client, tmp_path
):
    """Issue #87 on the CSV path: the header lists the requested columns."""
    respx_mock.get(PRICES_URL).respond(json=NO_DATA, status_code=404)

    path = client.stocks.prices(
        "AAPL",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "empty.csv",
        columns=["updated", "MID", "no_such_column"],
    )

    assert pathlib.Path(path).read_bytes() == b"updated,mid\r\n"


@pytest.mark.parametrize(
    ("columns", "index_name", "expected"),
    [
        (["t", "c"], "Date", ["Close"]),
        (["close", "Date", "CLOSE"], "Date", ["Close"]),
        (["price", "mark"], "Date", ["Open", "High", "Low", "Close", "Volume"]),
    ],
    ids=["api-names", "human-names-and-duplicates", "aliases-not-mirrored"],
)
def test_no_data_column_filter_on_a_human_readable_model(
    respx_mock, client, columns, index_name, expected
):
    """The API filters on its own names and renames afterwards, so a filter
    written in API names under `use_human_readable=True` selects the
    human-readable twins by position (#87). Its endpoint-dependent aliases
    (`price`, `mark`) are not mirrored: a filter made of them keeps the full
    set rather than producing a frame with no columns."""
    respx_mock.get(CANDLES_URL).respond(json=NO_DATA, status_code=404)

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        empty = client.stocks.candles(
            "AAPL",
            resolution="H",
            output_format=OutputFormat.DATAFRAME,
            use_human_readable=True,
            columns=columns,
        )

    assert empty.index.name == index_name
    assert list(empty.columns) == expected


def test_no_data_csv_without_headers_is_an_empty_file(respx_mock, client, tmp_path):
    respx_mock.get(PRICES_URL).respond(json=NO_DATA, status_code=404)

    path = client.stocks.prices(
        "AAPL",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "empty.csv",
        add_headers=False,
    )

    assert pathlib.Path(path).read_bytes() == b""


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
