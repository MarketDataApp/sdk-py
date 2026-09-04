"""CSV file handling on every resource.

#60: a caller-supplied filename must be the file that gets written and the
path that gets returned. #43: the filesystem is only touched when a CSV is
actually written, the write is an exclusive create, and the bytes are stored
exactly as the API sent them.
"""

import pathlib

import httpx
import pytest

from marketdata.input_types.base import OutputFormat

PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"
# RFC 4180 line endings, exactly as the API sends them.
CSV_BODY = (
    "s,symbol,mid,change,changepct,updated\r\nok,AAPL,150.5,1.5,0.01,1737072000\r\n"
)


@pytest.fixture
def prices_csv(respx_mock):
    respx_mock.get(PRICES_URL).respond(text=CSV_BODY, status_code=200)


def test_custom_filename_is_written_and_returned(prices_csv, client, tmp_path):
    output = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename="mine.csv"
    )

    written = pathlib.Path(output)
    assert written == (tmp_path / "mine.csv").absolute()
    # Byte-faithful on every platform: no newline translation on the way out.
    assert written.read_bytes() == CSV_BODY.encode()
    # Nothing was minted in output/ behind the caller's back.
    assert not (tmp_path / "output").exists()


def test_custom_filename_accepts_a_path_object(prices_csv, client, tmp_path):
    target = tmp_path / "prices.csv"

    output = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename=target
    )

    assert pathlib.Path(output) == target.absolute()
    assert target.read_bytes() == CSV_BODY.encode()


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
    assert not (tmp_path / "output").exists()

    output = client.stocks.prices("AAPL", output_format=OutputFormat.CSV)

    written = pathlib.Path(output)
    assert written.parent == (tmp_path / "output").absolute()
    assert written.suffix == ".csv"
    assert written.read_bytes() == CSV_BODY.encode()


def test_non_csv_requests_never_touch_the_filesystem(respx_mock, client, tmp_path):
    """#43: validation used to mkdir output/ on every request, whatever the
    output format and wherever the process happened to run."""
    respx_mock.get(PRICES_URL).respond(
        json={
            "s": "ok",
            "symbol": ["AAPL"],
            "mid": [150.5],
            "change": [1.5],
            "changepct": [0.01],
            "updated": [1737072000],
        },
        status_code=200,
    )

    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)

    assert not (tmp_path / "output").exists()
    assert list(tmp_path.iterdir()) == []


def test_a_file_that_appears_before_the_write_is_not_overwritten(
    respx_mock, client, tmp_path
):
    """#43: the exists-check runs before the request and the write happens
    after the response, so a path can appear in between. The write must be an
    exclusive create, never a silent overwrite."""
    target = tmp_path / "mine.csv"

    def _create_target_meanwhile(request: httpx.Request) -> httpx.Response:
        target.write_text("someone else's data")
        return httpx.Response(200, text=CSV_BODY)

    respx_mock.get(PRICES_URL).mock(side_effect=_create_target_meanwhile)

    with pytest.raises(FileExistsError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.CSV, filename=target)
    assert "mine.csv" in str(exc_info.value)
    assert target.read_text() == "someone else's data"


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
