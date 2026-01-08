import datetime
import pathlib
from unittest.mock import patch

import pytest
import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.input_types.funds import FundsCandlesInput
from marketdata.output_types.funds_candles import FundsCandle, FundsCandlesHumanReadable
from marketdata.sdk_error import MarketDataClientErrorResult


def test_fund_candle_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )

    instance = FundsCandle(
        t=timestamp,
        o=280.02,
        h=280.02,
        l=280.02,
        c=280.02,
    )

    assert isinstance(str(instance), str)


def test_funds_candles_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = FundsCandlesHumanReadable(
        Date=timestamp,
        Open=280.02,
        High=280.02,
        Low=280.02,
        Close=280.02,
    )
    assert isinstance(str(instance), str)


def test_funds_candles_input_validation():
    valid_inputs = [
        "1D",
        "1W",
        "1M",
        "1Y",
        "D",
        "W",
        "M",
        "Y",
        "y",
        "m",
        "1d",
        "1w",
        "1m",
        "1y",
    ]
    invalid_inputs = [
        "1H",
        "M14",
        "15x5",
        "15x5D",
        "15x5W",
        "15x5M",
        "15x5Y",
        "15x5y",
        "15x5m",
        "15x5d",
        "15x5w",
    ]

    for _input in valid_inputs:
        assert FundsCandlesInput(symbol="VFINX", resolution=_input).resolution == _input

    for _input in invalid_inputs:
        with pytest.raises(ValueError):
            FundsCandlesInput(symbol="VFINX", resolution=_input)


def test_funds_candles_input_dates_str():
    instance = FundsCandlesInput(
        symbol="VFINX", resolution="D", from_date="yesterday", to_date="today"
    )
    assert instance.from_date == "yesterday"
    assert instance.to_date == "today"


def test_get_funds_candles_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("funds_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/funds/candles/D/VFINX/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.funds.candles(
        symbol="VFINX",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
    )

    assert len(candles) == 7

    assert candles[0].t == datetime.datetime.fromtimestamp(1577941200, tz=pytz.timezone('US/Eastern'))
    assert candles[0].o == 300.69
    assert candles[0].h == 300.69
    assert candles[0].l == 300.69
    assert candles[0].c == 300.69


def test_get_funds_candles_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("funds_candles_response_200")
    respx_mock.get("https://api.marketdata.app/v1/funds/candles/D/VFINX/").respond(
        json=mock_data,
        status_code=200,
    )
    candles = client.funds.candles(
        symbol="VFINX", resolution="D", output_format=OutputFormat.JSON
    )
    assert candles == mock_data


def test_get_funds_candles_response_200_dataframe_pandas(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("funds_candles_response_200")

        respx_mock.get("https://api.marketdata.app/v1/funds/candles/D/VFINX/").respond(
            json=mock_data,
            status_code=200,
        )

        candles = client.funds.candles(
            symbol="VFINX",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
        )

        assert len(candles) == 7
        assert candles.index[0] == 1577941200
        assert candles.o.tolist()[0] == 300.69
        assert candles.h.tolist()[0] == 300.69
        assert candles.l.tolist()[0] == 300.69
        assert candles.c.tolist()[0] == 300.69


def test_get_funds_candles_response_200_dataframe_polars(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("funds_candles_response_200")

        respx_mock.get("https://api.marketdata.app/v1/funds/candles/D/VFINX/").respond(
            json=mock_data,
            status_code=200,
        )
        candles = client.funds.candles(
            symbol="VFINX",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
        )
        assert len(candles) == 7
        assert candles["t"][0] == 1577941200
        assert candles["o"][0] == 300.69
        assert candles["h"][0] == 300.69
        assert candles["l"][0] == 300.69
        assert candles["c"][0] == 300.69


def test_get_funds_candles_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("funds_candles_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/funds/candles/D/VFINX/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.funds.candles(
        symbol="VFINX",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
        use_human_readable=True,
    )

    assert len(candles) == 7
    assert candles[0].Date == datetime.datetime.fromtimestamp(1577941200, tz=pytz.timezone('US/Eastern'))
    assert candles[0].Open == 300.69
    assert candles[0].High == 300.69
    assert candles[0].Low == 300.69
    assert candles[0].Close == 300.69


def test_get_funds_candles_response_400(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/funds/candles/D/VFINX/").respond(
        json={"s": "error", "err": "invalid symbol"},
        status_code=400,
    )

    result = client.funds.candles(
        symbol="VFINX",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(result, MarketDataClientErrorResult)


def test_get_funds_candles_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/funds/candles/"],
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

    respx_mock.get("https://api.marketdata.app/v1/funds/candles/D/VFINX/").respond(
        json={},
        status_code=501,
    )

    candles = client.funds.candles(
        symbol="VFINX",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(candles, MarketDataClientErrorResult)


def test_get_funds_candles_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/funds/candles/D/VFINX/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    candles = client.funds.candles(
        symbol="VFINX", resolution="D", output_format=OutputFormat.CSV
    )
    assert pathlib.Path(candles).read_text() == "AS RECEIVED FROM API"
