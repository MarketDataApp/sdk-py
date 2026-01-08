import datetime
import pathlib
from unittest.mock import patch

import pytest
import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.output_types.options_strikes import (
    OptionsStrikes,
    OptionsStrikesHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult


def test_options_strikes_str():
    data = {
        "s": "ok",
        "updated": 1765478200,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikes(**data)
    assert isinstance(str(instance), str)


def test_options_strikes_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    data = {
        "Date": timestamp,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikesHumanReadable(**data)
    assert isinstance(str(instance), str)


def test_options_strikes_post_init():
    data = {
        "s": "ok",
        "updated": 1765478200,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikes(**data)
    instance.updated = 1765478200
    instance.__post_init__()
    assert instance.updated == datetime.datetime.fromtimestamp(1765478200, tz=pytz.timezone('US/Eastern'))


def test_options_strikes_to_float_list():
    data = {
        "s": "ok",
        "updated": 1765478200,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikes(**data)
    assert instance._to_float_list(
        "2025-12-12", [110.0, 120.0, 125.0, 130.0, 135.0]
    ) == [110.0, 120.0, 125.0, 130.0, 135.0]
    with pytest.raises(TypeError):
        instance._to_float_list("2025-12-12", "invalid")


def test_options_strikes_accepts_arbitrary_fields_only_float_list():
    data = {
        "s": "ok",
        "updated": 1765478200,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikes(**data)
    assert instance._to_float_list(
        "2025-12-12", [110.0, 120.0, 125.0, 130.0, 135.0]
    ) == [110.0, 120.0, 125.0, 130.0, 135.0]

    data["2025-12-12"] = "invalid"
    with pytest.raises(TypeError):
        OptionsStrikes(**data)


def test_options_strikes_human_readable_str():
    data = {
        "Date": 1765478200,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikesHumanReadable(**data)
    assert isinstance(str(instance), str)


def test_options_strikes_human_readable_post_init():
    data = {
        "Date": 1765478200,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikesHumanReadable(**data)
    instance.Date = 1765478200
    instance.__post_init__()
    assert instance.Date == datetime.datetime.fromtimestamp(1765478200, tz=pytz.timezone('US/Eastern'))


def test_options_strikes_human_readable_formats_timestamps():
    data = {
        "Date": 1765478200,
    }
    instance = OptionsStrikesHumanReadable(**data)
    assert instance.Date == datetime.datetime.fromtimestamp(1765478200, tz=pytz.timezone('US/Eastern'))
    data = {
        "Date": "2025-12-12",
    }
    instance = OptionsStrikesHumanReadable(**data)
    # fromisoformat returns naive datetime, so we compare with naive
    assert instance.Date == datetime.datetime.fromisoformat("2025-12-12")


def test_options_strikes_human_readable_to_float_list():
    data = {
        "Date": 1765478200,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikesHumanReadable(**data)
    assert instance._to_float_list(
        "2025-12-12", [110.0, 120.0, 125.0, 130.0, 135.0]
    ) == [110.0, 120.0, 125.0, 130.0, 135.0]
    with pytest.raises(TypeError):
        instance._to_float_list("2025-12-12", "invalid")


def test_options_strikes_human_readable_accepts_arbitrary_fields_only_float_list():
    data = {
        "Date": 1765478200,
        "2025-12-12": [110.0, 120.0, 125.0, 130.0, 135.0],
    }
    instance = OptionsStrikesHumanReadable(**data)
    assert instance._to_float_list(
        "2025-12-12", [110.0, 120.0, 125.0, 130.0, 135.0]
    ) == [110.0, 120.0, 125.0, 130.0, 135.0]

    data["2025-12-12"] = "invalid"
    with pytest.raises(TypeError):
        OptionsStrikesHumanReadable(**data)


def test_get_options_strikes_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("options_strikes_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/strikes/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    strikes = client.options.strikes("AAPL", output_format=OutputFormat.INTERNAL)
    assert isinstance(strikes, OptionsStrikes)
    assert strikes.s == "ok"
    assert strikes.updated == datetime.datetime.fromtimestamp(1765478200, tz=pytz.timezone('US/Eastern'))
    for key, value in strikes.__dict__.items():
        if key in ["s", "updated"]:
            continue
        assert value == mock_data[key]


def test_get_options_strikes_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("options_strikes_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/strikes/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    strikes = client.options.strikes("AAPL", output_format=OutputFormat.JSON)
    assert strikes == mock_data


def test_get_options_strikes_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("options_strikes_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/strikes/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    strikes = client.options.strikes(
        "AAPL", output_format=OutputFormat.INTERNAL, use_human_readable=True
    )
    assert strikes.Date == datetime.datetime.fromtimestamp(1765563517, tz=pytz.timezone('US/Eastern'))
    for key, value in strikes.__dict__.items():
        if key in ["Date"]:
            continue
        assert value == mock_data[key]


def test_get_options_strikes_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("options_strikes_response_200")

        respx_mock.get("https://api.marketdata.app/v1/options/strikes/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )

        strikes = client.options.strikes("AAPL", output_format=OutputFormat.DATAFRAME)
        assert strikes.updated[0] == 1765478200
        for key in strikes.columns:
            if key in ["s", "updated"]:
                continue
            assert list(strikes[key].dropna()) == mock_data[key]


def test_get_options_strikes_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("options_strikes_response_200")

        respx_mock.get("https://api.marketdata.app/v1/options/strikes/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )

        strikes = client.options.strikes("AAPL", output_format=OutputFormat.DATAFRAME)
        assert strikes["updated"][0] == 1765478200
        for key in strikes.columns:
            if key == "updated":
                continue
            assert strikes[key].drop_nulls().to_list() == mock_data[key]


def test_get_options_strikes_response_400(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/options/strikes/AAPL/").respond(
        json={},
        status_code=400,
    )

    result = client.options.strikes("AAPL", output_format=OutputFormat.INTERNAL)
    assert isinstance(result, MarketDataClientErrorResult)


def test_get_options_strikes_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/options/strikes/"],
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

    respx_mock.get("https://api.marketdata.app/v1/options/strikes/AAPL/").respond(
        json={},
        status_code=501,
    )

    strikes = client.options.strikes("AAPL", output_format=OutputFormat.INTERNAL)
    assert isinstance(strikes, MarketDataClientErrorResult)


def test_get_options_strikes_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/options/strikes/AAPL/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.options.strikes(
        "AAPL", output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
