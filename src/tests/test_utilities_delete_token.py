"""Tests for `DELETE /v1/user/token/` (new in 3.0.0): `client.utilities.delete_token()`.

This endpoint revokes the authenticated account's API token. Deleting the
live suite's own token would strand every other live test (and every future
run using the same shared secret), so unlike the other new-endpoint rules in
this delta, no live/integration test calls it for real; see the coder's
summary.
"""

import pathlib
from unittest.mock import patch

import pytest

from marketdata.exceptions import AuthenticationError, ParseError
from marketdata.input_types.base import OutputFormat
from marketdata.output_types.utilities_token import TokenDeleted

TOKEN_URL = "https://api.marketdata.app/v1/user/token/"


def test_token_deleted_model():
    deleted = TokenDeleted.from_dict({"s": "ok"})

    assert deleted.s == "ok"
    assert str(deleted) == "Token Deleted: ok"


def test_token_deleted_model_without_s_raises_type_error():
    """A body lacking `s` leaves the constructor without a required
    argument, a `TypeError`, not the bare `KeyError` a direct index would
    raise: `model_errors` only wraps `TypeError` and `ValueError` into
    `ParseError`."""
    with pytest.raises(TypeError):
        TokenDeleted.from_dict({})


def test_delete_utilities_token_response_without_s_is_a_parse_error(respx_mock, client):
    respx_mock.delete(TOKEN_URL).respond(json={}, status_code=200)

    with pytest.raises(ParseError):
        client.utilities.delete_token(output_format=OutputFormat.INTERNAL)


def test_delete_utilities_token_sends_a_delete_request(load_json, respx_mock, client):
    mock_data = load_json("utilities_delete_token_response_200")
    route = respx_mock.delete(TOKEN_URL).respond(json=mock_data, status_code=200)

    client.utilities.delete_token(output_format=OutputFormat.INTERNAL)

    assert route.calls.last.request.method == "DELETE"
    assert str(route.calls.last.request.url) == TOKEN_URL


def test_delete_utilities_token_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("utilities_delete_token_response_200")
    respx_mock.delete(TOKEN_URL).respond(json=mock_data, status_code=200)

    deleted = client.utilities.delete_token(output_format=OutputFormat.INTERNAL)

    assert isinstance(deleted, TokenDeleted)
    assert deleted.s == "ok"


def test_delete_utilities_token_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("utilities_delete_token_response_200")
    respx_mock.delete(TOKEN_URL).respond(json=mock_data, status_code=200)

    assert client.utilities.delete_token(output_format=OutputFormat.JSON) == mock_data


def test_delete_utilities_token_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    """`s` is never a column, in this resource as in every other one
    (`get_extra`'s convention): the only field this envelope carries leaves
    the frame with one row and no columns."""
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        mock_data = load_json("utilities_delete_token_response_200")
        respx_mock.delete(TOKEN_URL).respond(json=mock_data, status_code=200)

        df = client.utilities.delete_token(output_format=OutputFormat.DATAFRAME)

        assert df.shape == (1, 0)


def test_delete_utilities_token_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    """polars has no row with zero columns (unlike pandas, which keeps the
    index): dropping the only column collapses the frame to `(0, 0)`."""
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["polars"]):
        mock_data = load_json("utilities_delete_token_response_200")
        respx_mock.delete(TOKEN_URL).respond(json=mock_data, status_code=200)

        df = client.utilities.delete_token(output_format=OutputFormat.DATAFRAME)

        assert df.shape == (0, 0)


def test_delete_utilities_token_response_200_csv(load_json, respx_mock, client):
    """`s` is excluded from the CSV like everywhere else, and it is the only
    field this envelope carries, so the file is empty."""
    mock_data = load_json("utilities_delete_token_response_200")
    respx_mock.delete(TOKEN_URL).respond(json=mock_data, status_code=200)

    output = client.utilities.delete_token(
        output_format=OutputFormat.CSV, filename="token.csv"
    )

    assert pathlib.Path(output).read_text() == ""


def test_delete_utilities_token_response_unauthorized(respx_mock, client):
    respx_mock.delete(TOKEN_URL).respond(
        json={"s": "error", "errmsg": "Invalid token."}, status_code=401
    )

    with pytest.raises(AuthenticationError) as exc_info:
        client.utilities.delete_token(output_format=OutputFormat.INTERNAL)
    assert exc_info.value.status_code == 401
