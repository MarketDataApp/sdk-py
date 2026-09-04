import pathlib
from unittest.mock import patch

import pytest

from marketdata.client import MarketDataClient
from marketdata.exceptions import ServerError
from marketdata.input_types.base import OutputFormat
from marketdata.internal_settings import NO_TOKEN_VALUE
from marketdata.output_types.utilities_headers import RequestHeaders

HEADERS_URL = "https://api.marketdata.app/headers/"


def test_request_headers_model():
    headers = RequestHeaders.from_dict(
        {"User-Agent": "marketdata-sdk-py/1.3.0", "CF-Connecting-IP": "203.0.113.7"}
    )

    # Names are normalized to lowercase and looked up case-insensitively.
    assert headers.headers == {
        "user-agent": "marketdata-sdk-py/1.3.0",
        "cf-connecting-ip": "203.0.113.7",
    }
    assert headers.get("USER-AGENT") == "marketdata-sdk-py/1.3.0"
    assert headers.get("missing") is None
    assert headers.get("missing", "fallback") == "fallback"
    assert headers.user_agent == "marketdata-sdk-py/1.3.0"
    assert headers.detected_ip == "203.0.113.7"
    assert headers.authorization is None
    assert "user-agent: marketdata-sdk-py/1.3.0" in str(headers)


def test_request_headers_detected_ip_falls_back_to_x_real_ip():
    assert RequestHeaders.from_dict({"x-real-ip": "198.51.100.9"}).detected_ip == (
        "198.51.100.9"
    )
    assert RequestHeaders.from_dict({}).detected_ip is None


def test_get_utilities_headers_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("utilities_headers_response_200")
    route = respx_mock.get(HEADERS_URL).respond(json=mock_data, status_code=200)

    headers = client.utilities.headers(output_format=OutputFormat.INTERNAL)

    assert isinstance(headers, RequestHeaders)
    assert headers.user_agent == "marketdata-sdk-py/1.3.0"
    assert headers.detected_ip == "203.0.113.7"
    assert headers.authorization.startswith("Bearer ****")
    assert headers.get("cf-ray") == "a35612271fcb8f28"

    # The endpoint answers 404 to any query parameter, so the request is bare.
    assert str(route.calls.last.request.url) == HEADERS_URL


def test_get_utilities_headers_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("utilities_headers_response_200")
    respx_mock.get(HEADERS_URL).respond(json=mock_data, status_code=200)

    assert client.utilities.headers(output_format=OutputFormat.JSON) == mock_data


def test_get_utilities_headers_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        mock_data = load_json("utilities_headers_response_200")
        respx_mock.get(HEADERS_URL).respond(json=mock_data, status_code=200)

        df = client.utilities.headers(output_format=OutputFormat.DATAFRAME)

        assert df.shape == (1, len(mock_data))
        assert df["user-agent"].tolist() == ["marketdata-sdk-py/1.3.0"]


def test_get_utilities_headers_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["polars"]):
        mock_data = load_json("utilities_headers_response_200")
        respx_mock.get(HEADERS_URL).respond(json=mock_data, status_code=200)

        df = client.utilities.headers(output_format=OutputFormat.DATAFRAME)

        assert df.height == 1
        assert df["cf-connecting-ip"][0] == "203.0.113.7"


def test_get_utilities_headers_response_200_csv(load_json, respx_mock, client):
    mock_data = load_json("utilities_headers_response_200")
    respx_mock.get(HEADERS_URL).respond(json=mock_data, status_code=200)

    output = client.utilities.headers(
        output_format=OutputFormat.CSV, filename="headers.csv"
    )

    lines = pathlib.Path(output).read_text().splitlines()
    assert len(lines) == 2
    assert lines[0].split(",") == list(mock_data.keys())
    assert "marketdata-sdk-py/1.3.0" in lines[1]


def test_get_utilities_headers_works_in_demo_mode(load_json, respx_mock):
    mock_data = load_json("utilities_headers_response_200")
    route = respx_mock.get(HEADERS_URL).respond(json=mock_data, status_code=200)
    demo_client = MarketDataClient(token=NO_TOKEN_VALUE)

    headers = demo_client.utilities.headers(output_format=OutputFormat.INTERNAL)

    assert isinstance(headers, RequestHeaders)
    assert "Authorization" not in route.calls.last.request.headers


def test_get_utilities_headers_no_data_is_an_empty_result(respx_mock, client):
    respx_mock.get(HEADERS_URL).respond(json={"s": "no_data"}, status_code=404)

    assert client.utilities.headers(output_format=OutputFormat.INTERNAL) is None
    assert client.utilities.headers(output_format=OutputFormat.JSON) == {"s": "no_data"}


def test_get_utilities_headers_response_bad_status_code(respx_mock, client):
    respx_mock.get(HEADERS_URL).respond(
        json={"s": "error", "errmsg": "nope"}, status_code=500
    )

    with pytest.raises(ServerError) as exc_info:
        client.utilities.headers(output_format=OutputFormat.INTERNAL)
    assert exc_info.value.status_code == 500
