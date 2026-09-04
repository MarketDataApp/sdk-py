import pathlib
from unittest.mock import patch

import pytest

from marketdata.exceptions import AuthenticationError
from marketdata.input_types.base import OutputFormat
from marketdata.output_types.utilities_user import User
from marketdata.types import UserRateLimits

USER_URL = "https://api.marketdata.app/user/"


def test_user_model():
    user = User.from_dict(
        {
            "x-ratelimit-requests-remaining": 9500,
            "x-ratelimit-requests-limit": 10000,
            "x-options-data-permissions": "realtime",
            "some-future-field": "ignored",
        }
    )

    # The API body still says "requests"; the SDK speaks in API credits.
    assert user.credit_limit == 10000
    assert user.credits_remaining == 9500
    assert user.options_data_permissions == "realtime"
    assert user.has_options_data
    assert str(user) == "User: 9500/10000 credits remaining, options data: realtime"


def test_user_model_without_options_permissions():
    user = User(credit_limit=100, credits_remaining=100, options_data_permissions="")

    assert not user.has_options_data
    assert str(user).endswith("options data: none")


def test_get_utilities_user_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("utilities_user_response_200")
    route = respx_mock.get(USER_URL).respond(json=mock_data, status_code=200)

    user = client.utilities.user(output_format=OutputFormat.INTERNAL)

    assert isinstance(user, User)
    assert user.credit_limit == 10000
    assert user.credits_remaining == 9500
    assert user.options_data_permissions == "realtime"
    assert str(route.calls.last.request.url) == USER_URL


def test_get_utilities_user_refreshes_client_rate_limits(load_json, respx_mock, client):
    mock_data = load_json("utilities_user_response_200")
    respx_mock.get(USER_URL).respond(
        json=mock_data,
        status_code=200,
        headers={
            "x-api-ratelimit-limit": "10000",
            "x-api-ratelimit-remaining": "9500",
            "x-api-ratelimit-reset": "1737072000",
            "x-api-ratelimit-consumed": "0",
        },
    )
    # The conftest client patches header extraction at the instance level;
    # drop that so the real extraction runs.
    client.__dict__.pop("_extract_rate_limits", None)

    client.utilities.user(output_format=OutputFormat.INTERNAL)

    assert client.rate_limits.requests_limit == 10000
    assert client.rate_limits.requests_remaining == 9500


def test_get_utilities_user_is_not_blocked_by_exhausted_credits(
    load_json, respx_mock, client
):
    mock_data = load_json("utilities_user_response_200")
    respx_mock.get(USER_URL).respond(json=mock_data, status_code=200)
    client.rate_limits = UserRateLimits(
        requests_limit=100, requests_remaining=0, requests_reset=60, requests_consumed=1
    )

    user = client.utilities.user(output_format=OutputFormat.INTERNAL)

    assert isinstance(user, User)


def test_get_utilities_user_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("utilities_user_response_200")
    respx_mock.get(USER_URL).respond(json=mock_data, status_code=200)

    assert client.utilities.user(output_format=OutputFormat.JSON) == mock_data


def test_get_utilities_user_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        mock_data = load_json("utilities_user_response_200")
        respx_mock.get(USER_URL).respond(json=mock_data, status_code=200)

        df = client.utilities.user(output_format=OutputFormat.DATAFRAME)

        assert df.shape == (1, 3)
        assert df["x-ratelimit-requests-limit"].tolist() == [10000]


def test_get_utilities_user_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["polars"]):
        mock_data = load_json("utilities_user_response_200")
        respx_mock.get(USER_URL).respond(json=mock_data, status_code=200)

        df = client.utilities.user(output_format=OutputFormat.DATAFRAME)

        assert df.height == 1
        assert df["x-ratelimit-requests-remaining"][0] == 9500


def test_get_utilities_user_response_200_csv(load_json, respx_mock, client):
    mock_data = load_json("utilities_user_response_200")
    respx_mock.get(USER_URL).respond(json=mock_data, status_code=200)

    output = client.utilities.user(output_format=OutputFormat.CSV, filename="user.csv")

    lines = pathlib.Path(output).read_text().splitlines()
    assert lines == [
        "x-ratelimit-requests-remaining,x-ratelimit-requests-limit,x-options-data-permissions",
        "9500,10000,realtime",
    ]


def test_get_utilities_user_response_unauthorized(respx_mock, client):
    respx_mock.get(USER_URL).respond(
        json={"s": "error", "errmsg": "Invalid token."}, status_code=401
    )

    with pytest.raises(AuthenticationError) as exc_info:
        client.utilities.user(output_format=OutputFormat.INTERNAL)
    assert exc_info.value.status_code == 401
