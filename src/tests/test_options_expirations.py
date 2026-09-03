import datetime
import pathlib
from unittest.mock import patch

import pandas as pd
import pytz

from marketdata.input_types.base import (
    OutputFormat,
)
from marketdata.output_types.options_expirations import (
    OptionsExpirations,
    OptionsExpirationsHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult

ET = pytz.timezone("US/Eastern")


def test_options_expirations_str():
    timestamp = int(datetime.datetime(2025, 1, 1, 0, 0, 0, 0, ET).timestamp())

    instance = OptionsExpirations(
        s="ok",
        expirations=[timestamp],
        updated=timestamp,
    )

    assert isinstance(str(instance), str)


def test_options_expirations_human_readable_str():
    timestamp = int(datetime.datetime(2025, 1, 1, 0, 0, 0, 0, ET).timestamp())
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
    # Unix timestamps are converted to US/Eastern datetimes
    assert expirations.expirations[0] == datetime.datetime.fromtimestamp(
        1764910800, tz=ET
    )
    assert expirations.expirations[0].date() == datetime.date(2025, 12, 5)
    assert expirations.updated == datetime.datetime.fromtimestamp(1764941963, tz=ET)


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
    # Unix timestamps are converted to US/Eastern datetimes
    assert expirations.Expirations[0] == datetime.datetime.fromtimestamp(
        1765515600, tz=ET
    )
    assert expirations.Expirations[0].date() == datetime.date(2025, 12, 12)
    assert expirations.Date == datetime.datetime.fromtimestamp(1765561297, tz=ET)


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
        assert expirations["updated"].iloc[0] == datetime.datetime.fromtimestamp(
            1764941963, tz=ET
        )


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
        assert expirations["updated"][0] == datetime.datetime.fromtimestamp(
            1764941963, tz=ET
        )


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


def test_options_expirations_optional_updated():
    """Issue #23: the `updated` field must be optional so partial API
    responses (e.g. when filtering columns) don't raise.
    """
    instance = OptionsExpirations(
        s="ok",
        expirations=[1764910800],
        updated=None,
    )
    assert instance.updated is None
    assert isinstance(str(instance), str)


def test_get_options_expirations_columns_filter_dataframe_pandas(respx_mock, client):
    """Issue #23: requesting `columns=["expirations"]` makes the API return
    only that column. The result must NOT be an empty DataFrame with the data
    silently moved into the index.
    """
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        expiration_timestamps = [1764910800, 1765515600, 1766120400]
        # Server-side column filtering: only the requested column comes back.
        partial_data = {
            "s": "ok",
            "expirations": expiration_timestamps,
        }
        respx_mock.get(
            "https://api.marketdata.app/v1/options/expirations/AAPL/"
        ).respond(
            json=partial_data,
            status_code=200,
        )

        df = client.options.expirations(
            symbol="AAPL",
            output_format=OutputFormat.DATAFRAME,
            columns=["expirations"],
        )

        # The data must stay as an "expirations" column on a default
        # RangeIndex, not be silently promoted into the index.
        expected_df = pd.DataFrame(
            {
                "expirations": pd.to_datetime(
                    expiration_timestamps, unit="s", utc=True
                ).tz_convert(ET)
            }
        )
        pd.testing.assert_frame_equal(df, expected_df)


def test_get_options_expirations_columns_filter_dataframe_polars(respx_mock, client):
    """Issue #23 (regression guard for polars): filtering by a single column
    must keep the data accessible as a column.
    """
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        expiration_timestamps = [1764910800, 1765515600, 1766120400]
        partial_data = {
            "s": "ok",
            "expirations": expiration_timestamps,
        }
        respx_mock.get(
            "https://api.marketdata.app/v1/options/expirations/AAPL/"
        ).respond(
            json=partial_data,
            status_code=200,
        )

        df = client.options.expirations(
            symbol="AAPL",
            output_format=OutputFormat.DATAFRAME,
            columns=["expirations"],
        )

        # A single "expirations" column holding the timestamps converted to
        # US/Eastern datetimes, with nothing dropped.
        expected_expirations = [
            datetime.datetime.fromtimestamp(ts, tz=ET) for ts in expiration_timestamps
        ]
        assert df.columns == ["expirations"]
        assert df["expirations"].to_list() == expected_expirations


def test_get_options_expirations_partial_response_internal(respx_mock, client):
    """Issue #23: an INTERNAL response missing the `updated` field must parse
    successfully instead of failing and returning an error result.
    """
    expiration_timestamps = [1764910800, 1765515600, 1766120400]
    partial_data = {
        "s": "ok",
        "expirations": expiration_timestamps,
    }
    respx_mock.get("https://api.marketdata.app/v1/options/expirations/AAPL/").respond(
        json=partial_data,
        status_code=200,
    )

    expirations = client.options.expirations(
        symbol="AAPL", output_format=OutputFormat.INTERNAL
    )

    # The partial response parses, with timestamps converted to US/Eastern
    # datetimes and the absent `updated` field left as None.
    expected_expirations = [
        datetime.datetime.fromtimestamp(ts, tz=ET) for ts in expiration_timestamps
    ]
    assert isinstance(expirations, OptionsExpirations)
    assert expirations.s == "ok"
    assert expirations.expirations == expected_expirations
    assert expirations.updated is None


def test_get_options_expirations_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/options/expirations/AAPL/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.options.expirations(
        symbol="AAPL", output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
