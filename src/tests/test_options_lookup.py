import datetime

import pytz
import pathlib
from unittest.mock import patch

from marketdata.input_types.base import OutputFormat
from marketdata.input_types.options import LookupOptionSide
from marketdata.output_types.options_lookup import (
    OptionsLookup,
    OptionsLookupHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult


def test_options_lookup_str():
    instance = OptionsLookup(
        s="ok",
        optionSymbol="AAPL230728C00200000",
    )
    assert isinstance(str(instance), str)


def test_options_lookup_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = OptionsLookupHumanReadable(
        Symbol="AAPL230728C00200000",
    )
    assert isinstance(str(instance), str)


def test_get_options_lookup_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("options_lookup_response_200")

    respx_mock.get(
        "https://api.marketdata.app/v1/options/lookup/AAPL%2028-00-2023%20200.0%20call/"
    ).respond(
        json=mock_data,
        status_code=200,
    )

    lookup = client.options.lookup(
        "AAPL 28-00-2023 200.0 call", output_format=OutputFormat.INTERNAL
    )
    assert lookup.s == "ok"
    assert lookup.optionSymbol == "AAPL230728C00200000"


def test_get_options_lookup_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("options_lookup_response_200")

    respx_mock.get(
        "https://api.marketdata.app/v1/options/lookup/AAPL%2028-00-2023%20200.0%20call/",
    ).respond(
        json=mock_data,
        status_code=200,
    )
    lookup = client.options.lookup(
        "AAPL 28-00-2023 200.0 call", output_format=OutputFormat.JSON
    )
    assert lookup == mock_data


def test_get_options_lookup_response_200_human_readable(load_json, respx_mock, client):
    mock_data = load_json("options_lookup_human_response_200")

    respx_mock.get(
        "https://api.marketdata.app/v1/options/lookup/AAPL%2028-00-2023%20200.0%20call/",
    ).respond(
        json=mock_data,
        status_code=200,
    )
    lookup = client.options.lookup(
        "AAPL 28-00-2023 200.0 call",
        use_human_readable=True,
        output_format=OutputFormat.INTERNAL,
    )
    assert lookup.Symbol == "AAPL230728C00200000"


def test_get_options_lookup_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("options_lookup_response_200")

        respx_mock.get(
            "https://api.marketdata.app/v1/options/lookup/AAPL%2028-00-2023%20200.0%20call/"
        ).respond(
            json=mock_data,
            status_code=200,
        )

        lookup = client.options.lookup("AAPL 28-00-2023 200.0 call")
        assert len(lookup) == 1
        assert lookup.index.name == "optionSymbol"
        assert lookup.index.tolist() == ["AAPL230728C00200000"]


def test_get_options_lookup_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("options_lookup_response_200")

        respx_mock.get(
            "https://api.marketdata.app/v1/options/lookup/AAPL%2028-00-2023%20200.0%20call/"
        ).respond(
            json=mock_data,
            status_code=200,
        )
        lookup = client.options.lookup("AAPL 28-00-2023 200.0 call")
        assert len(lookup) == 1
        assert lookup["optionSymbol"][0] == "AAPL230728C00200000"


def test_get_options_lookup_response_400(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/lookup/AAPL 28-00-2023 200.0 call/"
    ).respond(
        json={"error": "Invalid symbol"},
        status_code=400,
    )
    lookup = client.options.lookup("AAPL 28-00-2023 200.0 call")
    assert isinstance(lookup, MarketDataClientErrorResult)


def test_get_options_lookup_status_offline(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/lookup/AAPL 28-00-2023 200.0 call/"
    ).respond(
        status_code=500,
    )
    lookup = client.options.lookup(
        symbol="AAPL",
        expiration_date=datetime.date(2023, 7, 28),
        strike_price=200.00,
        option_side=LookupOptionSide.CALL,
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(lookup, MarketDataClientErrorResult)


def test_get_options_lookup_response_200_csv(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/lookup/AAPL 28-00-2023 200.0 call/"
    ).respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.options.lookup(
        "AAPL 28-00-2023 200.0 call",
        output_format=OutputFormat.CSV,
        filename="test.csv",
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
