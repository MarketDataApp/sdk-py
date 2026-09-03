"""Regression tests for #60: a caller-supplied CSV filename must be the file
that gets written and the path that gets returned, on every resource."""

import pathlib

import pytest

from marketdata.input_types.base import OutputFormat

PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"
# Bare line feeds so the text-mode write/read round trip is identical on every
# platform (a "\r\n" body becomes "\r\r\n" on Windows, which is #43's territory).
CSV_BODY = "s,symbol,mid,change,changepct,updated\nok,AAPL,150.5,1.5,0.01,1737072000\n"


@pytest.fixture
def prices_csv(respx_mock):
    respx_mock.get(PRICES_URL).respond(text=CSV_BODY, status_code=200)


def test_custom_filename_is_written_and_returned(prices_csv, client, tmp_path):
    output = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename="mine.csv"
    )

    written = pathlib.Path(output)
    assert written == (tmp_path / "mine.csv").absolute()
    assert written.read_text() == CSV_BODY
    # Nothing was minted in output/ behind the caller's back.
    assert not (tmp_path / "output").exists()


def test_custom_filename_accepts_a_path_object(prices_csv, client, tmp_path):
    target = tmp_path / "prices.csv"

    output = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename=target
    )

    assert pathlib.Path(output) == target.absolute()
    assert target.read_text() == CSV_BODY


def test_client_default_filename_is_honored(prices_csv, client, tmp_path):
    client.default_params.filename = tmp_path / "from-defaults.csv"

    output = client.stocks.prices("AAPL", output_format=OutputFormat.CSV)

    assert pathlib.Path(output) == (tmp_path / "from-defaults.csv").absolute()


def test_call_filename_beats_client_default(prices_csv, client, tmp_path):
    client.default_params.filename = tmp_path / "from-defaults.csv"

    output = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename=tmp_path / "from-call.csv"
    )

    assert pathlib.Path(output) == (tmp_path / "from-call.csv").absolute()
    assert not (tmp_path / "from-defaults.csv").exists()


def test_without_filename_a_timestamped_file_is_created_in_output(
    prices_csv, client, tmp_path
):
    output = client.stocks.prices("AAPL", output_format=OutputFormat.CSV)

    written = pathlib.Path(output)
    assert written.parent == (tmp_path / "output").absolute()
    assert written.suffix == ".csv"
    assert written.read_text() == CSV_BODY


def test_custom_filename_is_honored_by_the_utilities_resource(
    respx_mock, client, tmp_path
):
    respx_mock.get("https://api.marketdata.app/user/").respond(
        json={
            "x-ratelimit-requests-remaining": 9500,
            "x-ratelimit-requests-limit": 10000,
            "x-options-data-permissions": "realtime",
        },
        status_code=200,
    )

    output = client.utilities.user(output_format=OutputFormat.CSV, filename="user.csv")

    assert pathlib.Path(output) == (tmp_path / "user.csv").absolute()
    assert not (tmp_path / "output").exists()
