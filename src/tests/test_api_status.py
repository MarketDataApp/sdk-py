import datetime
import time
from unittest.mock import MagicMock

import pytest

from marketdata.api_status import API_STATUS_DATA, APIStatusResult
from marketdata.internal_settings import (
    CACHE_VALIDITY_INTERVAL,
    REFRESH_API_STATUS_INTERVAL,
)

ALL_SERVICES = [
    "/v1/markets/status/",
    "/v1/options/chain/",
    "/v1/options/expirations/",
    "/v1/options/lookup/",
    "/v1/options/quotes/",
    "/v1/options/strikes/",
    "/v1/stocks/bulkcandles/",
    "/v1/stocks/bulkquotes/",
    "/v1/stocks/candles/",
    "/v1/stocks/earnings/",
    "/v1/stocks/news/",
    "/v1/stocks/quotes/",
]


def test_api_status_data(load_json, respx_mock, client):
    mock_data = load_json("api_status_response_200")
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json=mock_data, status_code=200
    )

    API_STATUS_DATA.refresh(client)
    for service in ALL_SERVICES:
        assert (
            API_STATUS_DATA.get_api_status(client, service)
            == APIStatusResult.ONLINE
        )


def test_api_status_data_offline(load_json, respx_mock, client):
    mock_data = load_json("api_status_response_200")
    mock_data["status"] = ["offline"] * len(mock_data["service"])
    mock_data["online"] = [False] * len(mock_data["service"])
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json=mock_data, status_code=200
    )

    API_STATUS_DATA.refresh(client)
    for service in ALL_SERVICES:
        assert (
            API_STATUS_DATA.get_api_status(client, service)
            == APIStatusResult.OFFLINE
        )


def test_api_status_data_unknown(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(status_code=500)

    API_STATUS_DATA.refresh(client)
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
        == APIStatusResult.UNKNOWN
    )


def test_api_status_data_service_not_online(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json={
            "s": "ok",
            "service": ["/v1/markets/status/"],
            "status": ["online"],
            "online": [False],
            "uptimePct30d": [0],
            "uptimePct90d": [0],
            "updated": [0],
        },
        status_code=200,
    )
    API_STATUS_DATA.refresh(client)
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
        == APIStatusResult.OFFLINE
    )


def test_api_status_data_service_not_found(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json={
            "s": "ok",
            "service": ["/v1/markets/status/"],
            "status": ["online"],
            "online": [True],
            "uptimePct30d": [100],
            "uptimePct90d": [100],
            "updated": [int(time.time())],
        },
        status_code=200,
    )

    API_STATUS_DATA.refresh(client)
    assert (
        API_STATUS_DATA.get_api_status(client, "invalid_service")
        == APIStatusResult.UNKNOWN
    )


def _populate_cache_with_age(age: datetime.timedelta):
    API_STATUS_DATA.service = ["/v1/markets/status/"]
    API_STATUS_DATA.status = ["online"]
    API_STATUS_DATA.online = [True]
    API_STATUS_DATA._last_refresh_at = datetime.datetime.now() - age


def test_get_api_status_fresh_cache_uses_cached_no_refresh(client, monkeypatch):
    _populate_cache_with_age(datetime.timedelta(seconds=10))
    triggered = []
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: triggered.append(c)
    )

    status = API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
    assert status == APIStatusResult.ONLINE
    assert triggered == []


def test_get_api_status_in_refresh_zone_uses_cache_and_triggers_refresh(
    client, monkeypatch
):
    age = REFRESH_API_STATUS_INTERVAL + datetime.timedelta(seconds=5)
    assert age < CACHE_VALIDITY_INTERVAL
    _populate_cache_with_age(age)
    triggered = []
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: triggered.append(c)
    )

    status = API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
    assert status == APIStatusResult.ONLINE
    assert triggered == [client]


def test_get_api_status_stale_cache_returns_unknown_and_triggers_refresh(
    client, monkeypatch
):
    _populate_cache_with_age(CACHE_VALIDITY_INTERVAL + datetime.timedelta(seconds=1))
    triggered = []
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: triggered.append(c)
    )

    status = API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
    assert status == APIStatusResult.UNKNOWN
    assert triggered == [client]


def test_get_api_status_empty_cache_returns_unknown_and_triggers_refresh(
    client, monkeypatch
):
    triggered = []
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: triggered.append(c)
    )

    status = API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
    assert status == APIStatusResult.UNKNOWN
    assert triggered == [client]


def test_trigger_async_refresh_skips_when_in_flight(client):
    API_STATUS_DATA._refresh_in_flight = True
    spawned = []

    def fake_thread(*args, **kwargs):
        spawned.append(kwargs)
        m = MagicMock()
        return m

    import marketdata.api_status as mod
    original_thread = mod.threading.Thread
    mod.threading.Thread = fake_thread
    try:
        API_STATUS_DATA._trigger_async_refresh(client)
        assert spawned == []
    finally:
        mod.threading.Thread = original_thread


def test_trigger_async_refresh_runs_in_background(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json={
            "service": ["/v1/markets/status/"],
            "status": ["online"],
            "online": [True],
            "uptimePct30d": [100],
            "uptimePct90d": [100],
            "updated": [int(time.time())],
        },
        status_code=200,
    )

    API_STATUS_DATA._trigger_async_refresh(client)
    thread = API_STATUS_DATA._refresh_thread
    assert thread is not None
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert API_STATUS_DATA._refresh_in_flight is False
    assert API_STATUS_DATA.service == ["/v1/markets/status/"]


def test_async_refresh_clears_in_flight_on_failure(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(status_code=500)

    API_STATUS_DATA._trigger_async_refresh(client)
    thread = API_STATUS_DATA._refresh_thread
    thread.join(timeout=5)
    assert API_STATUS_DATA._refresh_in_flight is False


def test_async_refresh_logs_unexpected_exception(client, monkeypatch):
    def boom(_):
        raise RuntimeError("network exploded")

    monkeypatch.setattr(API_STATUS_DATA, "refresh", boom)
    logged = []
    monkeypatch.setattr(
        client.logger, "exception", lambda msg, *a, **kw: logged.append(msg)
    )

    API_STATUS_DATA._trigger_async_refresh(client)
    thread = API_STATUS_DATA._refresh_thread
    thread.join(timeout=5)

    assert logged == ["Async status refresh failed"]
    assert API_STATUS_DATA._refresh_in_flight is False


def test_trigger_async_refresh_clears_flag_when_thread_construction_fails(
    client, monkeypatch
):
    def boom(*args, **kwargs):
        raise RuntimeError("cannot spawn")

    import marketdata.api_status as mod

    monkeypatch.setattr(mod.threading, "Thread", boom)

    with pytest.raises(RuntimeError):
        API_STATUS_DATA._trigger_async_refresh(client)

    assert API_STATUS_DATA._refresh_in_flight is False
