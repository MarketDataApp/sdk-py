"""Issue #83: the fan-out resources (`options.quotes`, one request per symbol;
`stocks.candles`, one request per chunk) retry each request on its own. A
failed request is re-issued alone, the healthy responses are kept, and the
decorator never re-runs the whole fan-out."""

from unittest.mock import patch

import httpx
import pytest

from marketdata.api_status import API_STATUS_DATA, APIStatusResult
from marketdata.exceptions import NetworkError, ServerError
from marketdata.input_types.base import OutputFormat

CANDLES_URL = "https://api.marketdata.app/v1/stocks/candles/H/AAPL/"
GOOD_URL = "https://api.marketdata.app/v1/options/quotes/AAPL250117C00150000/"
BAD_URL = "https://api.marketdata.app/v1/options/quotes/AAPL250117P00150000/"
SYMBOLS = ["AAPL250117C00150000", "AAPL250117P00150000"]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)


@pytest.fixture(autouse=True)
def _synchronous_status_refresh(monkeypatch):
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: API_STATUS_DATA.refresh(c)
    )


def test_a_failing_symbol_is_retried_alone(load_json, respx_mock, client):
    quotes = load_json("options_quotes_response_200")
    good = respx_mock.get(GOOD_URL).respond(json=quotes, status_code=200)
    bad = respx_mock.get(BAD_URL).mock(
        side_effect=[httpx.ConnectTimeout("slow"), httpx.Response(200, json=quotes)]
    )

    result = client.options.quotes(SYMBOLS, output_format=OutputFormat.INTERNAL)

    assert good.call_count == 1
    assert bad.call_count == 2
    assert len(result.optionSymbol) == 2 * len(quotes["optionSymbol"])


def test_an_unreachable_symbol_fails_the_call_without_re_sending_the_others(
    load_json, respx_mock, client
):
    quotes = load_json("options_quotes_response_200")
    good = respx_mock.get(GOOD_URL).respond(json=quotes, status_code=200)
    bad = respx_mock.get(BAD_URL).mock(side_effect=httpx.ConnectError("boom"))

    with pytest.raises(NetworkError) as exc_info:
        client.options.quotes(SYMBOLS, output_format=OutputFormat.INTERNAL)

    assert exc_info.value.request_url.startswith(BAD_URL)
    assert good.call_count == 1
    assert bad.call_count == client.max_retries + 1


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.OFFLINE,
)
def test_an_offline_service_stops_the_per_request_retry(
    _, load_json, respx_mock, client
):
    quotes = load_json("options_quotes_response_200")
    good = respx_mock.get(GOOD_URL).respond(json=quotes, status_code=200)
    bad = respx_mock.get(BAD_URL).respond(json={}, status_code=503)

    with pytest.raises(ServerError):
        client.options.quotes(SYMBOLS, output_format=OutputFormat.INTERNAL)

    assert good.call_count == 1
    assert bad.call_count == 1


def test_a_failing_candle_chunk_is_retried_alone(load_json, respx_mock, client):
    chunk = load_json("stocks_candles_response_200")
    route = respx_mock.get(CANDLES_URL).mock(
        side_effect=[
            httpx.Response(503, json={}),
            httpx.Response(200, json=chunk),
            httpx.Response(200, json=chunk),
        ]
    )

    candles = client.stocks.candles(
        "AAPL",
        resolution="H",
        from_date="2023-01-01",
        to_date="2024-06-01",
        output_format=OutputFormat.INTERNAL,
    )

    # Two chunks, one of them re-issued once: three requests, not four.
    assert route.call_count == 3
    assert len(candles) == 2 * len(chunk["t"])


def test_an_unreachable_candle_chunk_fails_the_call_without_re_sending_the_others(
    load_json, respx_mock, client
):
    chunk = load_json("stocks_candles_response_200")
    calls = []

    def _answer(request):
        chunk_start = request.url.params["from"][:10]
        calls.append(chunk_start)
        if chunk_start == "2023-01-01":
            return httpx.Response(200, json=chunk)
        raise httpx.ConnectError("boom")

    respx_mock.get(CANDLES_URL).mock(side_effect=_answer)

    with pytest.raises(NetworkError):
        client.stocks.candles(
            "AAPL",
            resolution="H",
            from_date="2023-01-01",
            to_date="2024-06-01",
            output_format=OutputFormat.INTERNAL,
        )

    assert calls.count("2023-01-01") == 1
    assert len(calls) == 1 + client.max_retries + 1
