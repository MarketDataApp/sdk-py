"""Issue #64: one fixed request timeout for every request the SDK makes, 99
seconds with a 2 second connect (SDK requirements §10), not configurable."""

import inspect

import httpx
import pytest

from marketdata.api_status import API_STATUS_DATA
from marketdata.client import MarketDataClient
from marketdata.exceptions import NetworkError
from marketdata.input_types.base import OutputFormat
from marketdata.internal_settings import REQUEST_TIMEOUT

PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"
QUOTES_URL = "https://api.marketdata.app/v1/options/quotes/"
EXPECTED = {"connect": 2.0, "read": 99.0, "write": 99.0, "pool": 99.0}


def timeouts_of(respx_mock):
    """What each request actually handed to httpx. `Client.request(timeout=)`
    lands in the request's extensions, which is the value the transport reads,
    so this is the timeout that was in force rather than the one we passed."""
    return [call.request.extensions["timeout"] for call in respx_mock.calls]


def test_the_timeout_constant_is_the_one_the_spec_fixes():
    assert isinstance(REQUEST_TIMEOUT, httpx.Timeout)
    assert REQUEST_TIMEOUT.connect == 2.0
    assert REQUEST_TIMEOUT.read == REQUEST_TIMEOUT.write == REQUEST_TIMEOUT.pool == 99.0


def test_the_client_itself_carries_the_timeout(client):
    """On the `httpx.Client`, not on each call site: httpx defaults to 5
    seconds, so anything reaching this object another way used a bound nobody
    chose."""
    assert client.client.timeout == REQUEST_TIMEOUT


def test_every_request_of_a_call_carries_it(load_json, respx_mock, client):
    """Including the `/user/` call the client makes at start-up and each
    request of a fan-out, which is where a bound of its own would hide."""
    respx_mock.get(url__regex=r".*/options/quotes/.*").respond(
        json=load_json("options_quotes_response_200"), status_code=200
    )

    client.options.quotes(
        ["AAPL250117C00150000", "AAPL250117P00150000"],
        output_format=OutputFormat.JSON,
    )

    timeouts = timeouts_of(respx_mock)
    # `/user/` at start-up and one request per symbol.
    assert len(timeouts) == 3
    assert all(timeout == EXPECTED for timeout in timeouts)


def test_the_status_refresh_carries_it_too(respx_mock, client):
    """The one request no resource makes: the service-status refresh, issued
    from a daemon thread. At 99 seconds it can hold the refresh flag for that
    long, which is worth knowing rather than discovering."""
    API_STATUS_DATA.refresh(client)

    status_calls = [
        call for call in respx_mock.calls if call.request.url.path == "/status/"
    ]
    assert status_calls
    assert all(call.request.extensions["timeout"] == EXPECTED for call in status_calls)


def test_a_connect_timeout_is_a_network_error_and_is_retried(
    respx_mock, client, monkeypatch
):
    """The 2 second connect bound is only useful if giving up on it is a
    failure the SDK names and retries (SDK requirements §9.2)."""
    monkeypatch.setattr("time.sleep", lambda *_: None)
    route = respx_mock.get(PRICES_URL).mock(
        side_effect=httpx.ConnectTimeout("timed out", request=None)
    )

    with pytest.raises(NetworkError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert "ConnectTimeout" in exc_info.value.message
    assert route.call_count == client.max_retries + 1


def test_a_read_timeout_is_a_network_error(respx_mock, client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    respx_mock.get(PRICES_URL).mock(
        side_effect=httpx.ReadTimeout("too slow", request=None)
    )

    with pytest.raises(NetworkError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert "ReadTimeout" in exc_info.value.message


def test_the_timeout_cannot_be_configured():
    """§10 calls for a fixed timeout, so neither the constructor nor the
    request helper takes one: a resource that wanted a longer wait would be
    able to outlive the API's own limit."""
    assert "timeout" not in inspect.signature(MarketDataClient.__init__).parameters
    assert "timeout" not in inspect.signature(MarketDataClient._make_request).parameters
