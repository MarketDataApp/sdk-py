import datetime
import pathlib
from unittest.mock import patch

import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.input_types.markets import MarketStatusInput
from marketdata.output_types.markets_status import (
    MarketStatus,
    MarketStatusHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult


def test_markets_status_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )

    instance = MarketStatus(
        date=timestamp,
        status="open",
    )

    assert isinstance(str(instance), str)


def test_markets_status_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = MarketStatusHumanReadable(
        Date=timestamp,
        Status="open",
    )
    assert isinstance(str(instance), str)


def test_markets_status_input_dates_str():
    instance = MarketStatusInput(
        from_date="yesterday",
        to_date="today",
    )
    assert instance.from_date == "yesterday"
    assert instance.to_date == "today"


def test_get_markets_status_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("markets_status_response_200")

    respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
        json=mock_data,
        status_code=200,
    )

    status_list = client.markets.status(
        output_format=OutputFormat.INTERNAL,
    )

    assert status_list[0].status == "closed"
    # format_timestamp now returns US/Eastern, so compare directly
    expected = datetime.datetime.fromtimestamp(1735707600, tz=pytz.timezone('US/Eastern'))
    assert status_list[0].date == expected
    assert str(status_list[0]) == "Market Status: closed, Date: 2025-01-01 00:00:00-05:00"


def test_get_markets_status_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("markets_status_response_200")

    respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
        json=mock_data,
        status_code=200,
    )
    status_list = client.markets.status(output_format=OutputFormat.JSON)
    assert status_list == mock_data


def test_get_markets_status_response_200_human_readable(load_json, respx_mock, client):
    mock_data = load_json("markets_status_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
        json=mock_data,
        status_code=200,
    )

    status_list = client.markets.status(
        output_format=OutputFormat.INTERNAL,
        use_human_readable=True,
    )

    assert status_list[0].Status == "closed"
    # format_timestamp now returns US/Eastern, so compare directly
    expected = datetime.datetime.fromtimestamp(1735707600, tz=pytz.timezone('US/Eastern'))
    assert status_list[0].Date == expected
    assert str(status_list[0]) == "Market Status: closed, Date: 2025-01-01 00:00:00-05:00"


def test_get_markets_status_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("markets_status_response_200")

        respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
            json=mock_data,
            status_code=200,
        )

        status_df = client.markets.status(
            output_format=OutputFormat.DATAFRAME,
        )

        assert status_df.index.tolist()[0] == 1735707600
        assert status_df.status.tolist()[0] == "closed"
        assert status_df.index.name == "date"


def test_get_markets_status_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("markets_status_response_200")

        respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
            json=mock_data,
            status_code=200,
        )
        status_df = client.markets.status(
            output_format=OutputFormat.DATAFRAME,
        )

        assert status_df["date"][0] == 1735707600
        assert status_df["status"][0] == "closed"


def test_get_markets_status_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )

    result = client.markets.status(
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "Request failed with: Test error message"


def test_get_markets_status_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/markets/status/"],
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

    respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
        json={},
        status_code=501,
    )

    status_list = client.markets.status(
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(status_list, MarketDataClientErrorResult)


def test_get_markets_status_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/markets/status/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.markets.status(
        output_format=OutputFormat.CSV,
        filename="test.csv",
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
