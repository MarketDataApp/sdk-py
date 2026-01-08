from unittest.mock import patch

import pytest

from marketdata.api_error import api_error_handler
from marketdata.exceptions import RequestError
from marketdata.resources.base import BaseResource
from src.marketdata.api_status import APIStatusResult


class DummyResource(BaseResource):
    @api_error_handler
    def test_function_fails(self):
        raise RequestError("test exception")


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.OFFLINE,
)
@patch(
    "marketdata.api_error.get_retry_adapter",
    return_value=lambda x, *args, **kwargs: x(*args, **kwargs),
)
def test_api_error_handler_fails_when_api_is_offline(
    retry_adapter, api_status_data, client
):
    resource = DummyResource(client=client)
    with pytest.raises(RequestError):
        resource.test_function_fails()
    retry_adapter.assert_not_called()


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.ONLINE,
)
@patch(
    "marketdata.api_error.get_retry_adapter",
    return_value=lambda x, *args, **kwargs: x(*args, **kwargs),
)
def test_api_error_handler_fails_when_api_is_online(
    retry_adapter, api_status_data, client
):
    resource = DummyResource(client=client)
    with pytest.raises(RequestError):
        resource.test_function_fails()
    retry_adapter.assert_called_once()


@patch(
    "marketdata.api_error.API_STATUS_DATA.get_api_status",
    return_value=APIStatusResult.UNKNOWN,
)
@patch(
    "marketdata.api_error.get_retry_adapter",
    return_value=lambda x, *args, **kwargs: x(*args, **kwargs),
)
def test_api_error_handler_fails_when_api_is_unknown(
    retry_adapter, api_status_data, client
):
    resource = DummyResource(client=client)
    with pytest.raises(RequestError):
        resource.test_function_fails()
    retry_adapter.assert_called_once()
