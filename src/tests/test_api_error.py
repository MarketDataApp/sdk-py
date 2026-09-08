from unittest.mock import patch

import pytest
from httpx import Request, Response

from marketdata.api_error import api_error_handler
from marketdata.api_status import APIStatusResult
from marketdata.exceptions import ServerError
from marketdata.resources.base import BaseResource


class DummyResource(BaseResource):
    call_count = 0

    @api_error_handler
    def test_function_fails(self):
        DummyResource.call_count += 1
        request = Request(method="GET", url="https://example.com")
        response = Response(status_code=502)
        raise ServerError("test exception", request=request, response=response)

    @api_error_handler(retry=False)
    def test_function_retries_itself(self):
        DummyResource.call_count += 1
        request = Request(method="GET", url="https://example.com")
        response = Response(status_code=502)
        raise ServerError("test exception", request=request, response=response)


@pytest.fixture(autouse=True)
def _reset_dummy():
    DummyResource.call_count = 0
    yield
    DummyResource.call_count = 0


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.OFFLINE,
)
def test_api_error_handler_offline_aborts_after_first_failure(_, client):
    resource = DummyResource(client=client)
    with pytest.raises(ServerError):
        resource.test_function_fails()
    assert DummyResource.call_count == 1


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.ONLINE,
)
def test_api_error_handler_online_retries_max_attempts(_, client):
    resource = DummyResource(client=client)
    with pytest.raises(ServerError):
        resource.test_function_fails()
    assert DummyResource.call_count == 4


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.UNKNOWN,
)
def test_api_error_handler_unknown_retries_max_attempts(_, client):
    resource = DummyResource(client=client)
    with pytest.raises(ServerError):
        resource.test_function_fails()
    assert DummyResource.call_count == 4


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.ONLINE,
)
def test_api_error_handler_respects_max_retries_zero(_, client):
    client.max_retries = 0
    resource = DummyResource(client=client)
    with pytest.raises(ServerError):
        resource.test_function_fails()
    assert DummyResource.call_count == 1


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.ONLINE,
)
def test_api_error_handler_without_retry_calls_once(_, client):
    """Issue #83: a resource that retries its own requests opts out of the
    retry around the whole call; the failure is still logged and raised."""
    resource = DummyResource(client=client)
    with pytest.raises(ServerError):
        resource.test_function_retries_itself()
    assert DummyResource.call_count == 1
