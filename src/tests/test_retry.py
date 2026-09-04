import datetime
from unittest.mock import MagicMock

import pytest
from httpx import Headers, Request, Response

from marketdata.exceptions import ServerError
from marketdata.retry import get_retry_adapter, parse_retry_after


def _make_retry_state(attempt_number: int, exc: Exception | None):
    outcome = None
    if exc is not None:
        outcome = MagicMock()
        outcome.exception.return_value = exc
    return type("S", (), {"attempt_number": attempt_number, "outcome": outcome})()


def _retry_after_response(value: str) -> Response:
    request = Request(method="GET", url="https://example.com")
    return Response(
        status_code=503, request=request, headers=Headers({"Retry-After": value})
    )


def test_get_retry_adapter(client):
    retry_adapter = get_retry_adapter(
        attempts=4,
        initial_delay=1.0,
        exceptions=[],
        logger=client.logger,
    )
    assert retry_adapter is not None
    assert retry_adapter.stop.max_attempt_number == 4
    assert retry_adapter.retry.exception_types == (Exception,)
    assert retry_adapter.reraise == False

    state = _make_retry_state(attempt_number=1, exc=None)
    assert retry_adapter.wait(state) == 1.0
    state.attempt_number = 2
    assert retry_adapter.wait(state) == 2.0
    state.attempt_number = 3
    assert retry_adapter.wait(state) == 4.0


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("0", 0.0),
        ("120", 120.0),
        ("3.5", 3.5),
        ("-5", 0.0),
        ("not-a-date", None),
        ("nan", None),
        ("inf", None),
        ("-inf", None),
    ],
)
def test_parse_retry_after_seconds(value, expected):
    assert parse_retry_after(value) == expected


def test_parse_retry_after_http_date_future():
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=60
    )
    header = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    result = parse_retry_after(header)
    assert result is not None
    assert 55 < result <= 60


def test_parse_retry_after_http_date_past():
    assert parse_retry_after("Wed, 21 Oct 1995 07:28:00 GMT") == 0.0


def test_parse_retry_after_naive_asctime_treated_as_utc():
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=120
    )
    header = future.strftime("%a %b %d %H:%M:%S %Y")
    result = parse_retry_after(header)
    assert result is not None
    assert 110 < result <= 120


def test_compute_wait_retry_after_overrides_exponential(client):
    retry_adapter = get_retry_adapter(
        attempts=4,
        initial_delay=1.0,
        exceptions=[ServerError],
        logger=client.logger,
    )
    exc = ServerError(
        "boom",
        request=Request(method="GET", url="https://example.com"),
        response=_retry_after_response("7"),
    )
    state = _make_retry_state(attempt_number=2, exc=exc)
    assert retry_adapter.wait(state) == 7.0


def test_compute_wait_no_retry_after_falls_back_to_exponential(client):
    retry_adapter = get_retry_adapter(
        attempts=4,
        initial_delay=1.0,
        exceptions=[ServerError],
        logger=client.logger,
    )
    request = Request(method="GET", url="https://example.com")
    exc = ServerError(
        "boom",
        request=request,
        response=Response(status_code=503, request=request),
    )
    state = _make_retry_state(attempt_number=3, exc=exc)
    assert retry_adapter.wait(state) == 4.0


def test_compute_wait_invalid_retry_after_falls_back(client):
    retry_adapter = get_retry_adapter(
        attempts=4,
        initial_delay=1.0,
        exceptions=[ServerError],
        logger=client.logger,
    )
    exc = ServerError(
        "boom",
        request=Request(method="GET", url="https://example.com"),
        response=_retry_after_response("garbage"),
    )
    state = _make_retry_state(attempt_number=1, exc=exc)
    assert retry_adapter.wait(state) == 1.0


def test_compute_wait_exception_without_response_falls_back(client):
    retry_adapter = get_retry_adapter(
        attempts=4,
        initial_delay=1.0,
        exceptions=[Exception],
        logger=client.logger,
    )
    state = _make_retry_state(attempt_number=2, exc=Exception("network down"))
    assert retry_adapter.wait(state) == 2.0
