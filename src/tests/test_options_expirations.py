import datetime
import pathlib
from unittest.mock import patch

import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.output_types.options_expirations import (
    OptionsExpirations,
    OptionsExpirationsHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult


def test_options_expirations_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )

    instance = OptionsExpirations(
        s="ok",
        expirations=["2025-01-01"],
        updated=timestamp,
    )

    assert isinstance(str(instance), str)


def test_options_expirations_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = OptionsExpirationsHumanReadable(
        Expirations=[timestamp],
        Date=timestamp,
    )
    assert isinstance(str(instance), str)


def test_get_options_expirations_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("options_expirations_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/expirations/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    expirations = client.options.expirations(
        symbol="AAPL", output_format=OutputFormat.INTERNAL
    )
    assert expirations.s == "ok"
    assert len(expirations.expirations) == 22
    # Date strings are parsed as naive datetimes by format_timestamp
    assert expirations.expirations[0] == datetime.datetime(2025, 12, 5, 0, 0)
    # API returns UTC, convert to US/Eastern for comparison
    expected = datetime.datetime(2025, 12, 5, 13, 39, 23, tzinfo=datetime.timezone.utc).astimezone(pytz.timezone('US/Eastern'))
    assert expirations.updated.astimezone(pytz.timezone('US/Eastern')) == expected


def test_get_options_expirations_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("options_expirations_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/expirations/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    expirations = client.options.expirations(
        symbol="AAPL", output_format=OutputFormat.JSON
    )
    assert expirations == mock_data


def test_get_options_expirations_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("options_expirations_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/expirations/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    expirations = client.options.expirations(
        symbol="AAPL", output_format=OutputFormat.INTERNAL, use_human_readable=True
    )
    # Date strings are parsed as naive datetimes by format_timestamp
    assert expirations.Expirations[0] == datetime.datetime(2025, 12, 12, 0, 0)
    # API returns UTC, convert to US/Eastern for comparison
    expected = datetime.datetime(2025, 12, 12, 17, 41, 37, tzinfo=datetime.timezone.utc).astimezone(pytz.timezone('US/Eastern'))
    assert expirations.Date.astimezone(pytz.timezone('US/Eastern')) == expected


def test_get_options_expirations_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("options_expirations_response_200")

        respx_mock.get(
            "https://api.marketdata.app/v1/options/expirations/AAPL/"
        ).respond(
            json=mock_data,
            status_code=200,
        )

        expirations = client.options.expirations(
            symbol="AAPL", output_format=OutputFormat.DATAFRAME
        )
        assert "s" not in expirations.columns
        assert len(expirations) == 22
        assert expirations["updated"].iloc[0] == 1764941963


def test_get_options_expirations_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("options_expirations_response_200")

        respx_mock.get(
            "https://api.marketdata.app/v1/options/expirations/AAPL/"
        ).respond(
            json=mock_data,
            status_code=200,
        )
        expirations = client.options.expirations(
            symbol="AAPL", output_format=OutputFormat.DATAFRAME
        )
        assert "s" not in expirations.columns
        assert len(expirations) == 22
        assert expirations["updated"][0] == 1764941963


def test_get_options_expirations_response_400(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/options/expirations/AAPL/").respond(
        json={},
        status_code=400,
    )

    result = client.options.expirations(
        symbol="AAPL", output_format=OutputFormat.INTERNAL
    )
    assert isinstance(result, MarketDataClientErrorResult)


def test_get_options_expirations_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/options/expirations/"],
        "status": ["offline"],
        "online": [False],
        "uptimePct30d": [0],
        "uptimePct90d": [0],
        "updated": [0],
    }

    respx_mock.get("https://api.marketdata.app/status/").respond(
        json=mock_data,
        status_code=200,
    )

    respx_mock.get("https://api.marketdata.app/v1/options/expirations/AAPL/").respond(
        json={},
        status_code=501,
    )

    expirations = client.options.expirations(
        symbol="AAPL", output_format=OutputFormat.INTERNAL
    )
    assert isinstance(expirations, MarketDataClientErrorResult)


def test_get_options_expirations_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/options/expirations/AAPL/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.options.expirations(
        symbol="AAPL", output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
