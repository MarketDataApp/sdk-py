import datetime
import pathlib
from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytz

from marketdata.api_status import API_STATUS_DATA
from marketdata.client import MarketDataClient
from marketdata.exceptions import BadStatusCodeError
from marketdata.input_types.base import OutputFormat
from marketdata.internal_settings import NO_TOKEN_VALUE
from marketdata.output_types.utilities_status import ServiceStatus
from marketdata.types import UserRateLimits

STATUS_URL = "https://api.marketdata.app/status/"
ET = pytz.timezone("US/Eastern")


def _service(**overrides) -> ServiceStatus:
    data = dict(
        service="/v1/stocks/quotes/",
        status="online",
        online=True,
        uptimePct30d=0.9999,
        uptimePct90d=0.995,
        updated=1735707600,
    )
    data.update(overrides)
    return ServiceStatus(**data)


def test_service_status_str():
    service = _service()
    assert isinstance(service.updated, datetime.datetime)
    assert service.is_online
    text = str(service)
    assert "/v1/stocks/quotes/" in text
    assert "99.99%" in text


def test_service_status_is_online_needs_both_flags():
    assert not _service(online=False).is_online
    assert not _service(status="offline").is_online


def test_get_utilities_status_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("utilities_status_response_200")
    route = respx_mock.get(STATUS_URL).respond(json=mock_data, status_code=200)

    statuses = client.utilities.status(output_format=OutputFormat.INTERNAL)

    assert isinstance(statuses, list)
    assert len(statuses) == 3
    assert all(isinstance(entry, ServiceStatus) for entry in statuses)
    assert statuses[0].service == "/v1/markets/status/"
    assert statuses[0].is_online
    assert statuses[2].service == "/v1/stocks/quotes/"
    assert not statuses[2].is_online
    assert statuses[0].updated == datetime.datetime.fromtimestamp(1735707600, tz=ET)

    # The endpoint answers 404 to any query parameter, so the request is bare.
    assert str(route.calls.last.request.url) == STATUS_URL


def test_get_utilities_status_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("utilities_status_response_200")
    respx_mock.get(STATUS_URL).respond(json=mock_data, status_code=200)

    assert client.utilities.status(output_format=OutputFormat.JSON) == mock_data


def test_get_utilities_status_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        mock_data = load_json("utilities_status_response_200")
        respx_mock.get(STATUS_URL).respond(json=mock_data, status_code=200)

        df = client.utilities.status(output_format=OutputFormat.DATAFRAME)

        assert df.index.name == "service"
        assert "s" not in df.columns
        assert df.loc["/v1/stocks/quotes/", "status"] == "offline"
        assert df.loc[
            "/v1/markets/status/", "updated"
        ] == datetime.datetime.fromtimestamp(1735707600, tz=ET)


def test_get_utilities_status_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["polars"]):
        mock_data = load_json("utilities_status_response_200")
        respx_mock.get(STATUS_URL).respond(json=mock_data, status_code=200)

        df = client.utilities.status(output_format=OutputFormat.DATAFRAME)

        assert df["service"][0] == "/v1/markets/status/"
        assert df["status"][2] == "offline"
        assert df["updated"][0] == datetime.datetime.fromtimestamp(1735707600, tz=ET)


def test_get_utilities_status_response_200_csv(load_json, respx_mock, client):
    mock_data = load_json("utilities_status_response_200")
    respx_mock.get(STATUS_URL).respond(json=mock_data, status_code=200)

    output = client.utilities.status(
        output_format=OutputFormat.CSV, filename="status.csv"
    )

    lines = pathlib.Path(output).read_text().splitlines()
    assert lines[0] == "service,status,online,uptimePct30d,uptimePct90d,updated"
    assert len(lines) == 4
    assert lines[3].startswith("/v1/stocks/quotes/,offline,False,")


def test_get_utilities_status_is_not_blocked_by_exhausted_credits(
    load_json, respx_mock, client
):
    mock_data = load_json("utilities_status_response_200")
    respx_mock.get(STATUS_URL).respond(json=mock_data, status_code=200)
    client.rate_limits = UserRateLimits(
        requests_limit=100, requests_remaining=0, requests_reset=60, requests_consumed=1
    )

    statuses = client.utilities.status(output_format=OutputFormat.INTERNAL)

    assert isinstance(statuses, list)
    assert len(statuses) == 3


def test_get_utilities_status_works_in_demo_mode(load_json, respx_mock):
    mock_data = load_json("utilities_status_response_200")
    route = respx_mock.get(STATUS_URL).respond(json=mock_data, status_code=200)
    demo_client = MarketDataClient(token=NO_TOKEN_VALUE)

    statuses = demo_client.utilities.status(output_format=OutputFormat.INTERNAL)

    assert len(statuses) == 3
    assert "Authorization" not in route.calls.last.request.headers


def test_get_utilities_status_response_bad_status_code(respx_mock, client):
    respx_mock.get(STATUS_URL).respond(json={"s": "no_data"}, status_code=404)

    with pytest.raises(BadStatusCodeError) as exc_info:
        client.utilities.status(output_format=OutputFormat.INTERNAL)
    assert exc_info.value.status_code == 404


def test_get_utilities_status_retries_without_consulting_the_status_cache(
    load_json, respx_mock, client, monkeypatch
):
    """The utilities endpoints have no entry in the /status/ service list, so
    a retry must not try to look one up (and must not log a bogus error)."""
    monkeypatch.setattr("time.sleep", lambda *_: None)
    status_lookup = MagicMock()
    monkeypatch.setattr(API_STATUS_DATA, "get_api_status", status_lookup)
    mock_data = load_json("utilities_status_response_200")
    respx_mock.get(STATUS_URL).mock(
        side_effect=[
            httpx.Response(502, json={}),
            httpx.Response(200, json=mock_data),
        ]
    )

    statuses = client.utilities.status(output_format=OutputFormat.INTERNAL)

    assert len(statuses) == 3
    status_lookup.assert_not_called()
    status_calls = [c for c in respx_mock.calls if c.request.url.path == "/status/"]
    assert len(status_calls) == 2
