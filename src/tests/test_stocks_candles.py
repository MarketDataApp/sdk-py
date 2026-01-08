import datetime
import pathlib
from unittest.mock import patch

import pytest
import pytz
from freezegun import freeze_time

from marketdata.input_types.base import OutputFormat
from marketdata.input_types.stocks import StocksCandlesInput
from marketdata.output_types.stocks_candles import (
    StockCandle,
    StockCandlesHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult


def test_stock_candle_str():
    instance = StockCandle(
        t=1577941200,
        o=[280.02],
        h=[280.02],
        l=[280.02],
        c=[280.02],
        v=[100],
    )
    assert isinstance(str(instance), str)


def test_stocks_candles_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    data = {
        "Date": timestamp,
        "Open": 280.02,
        "High": 280.02,
        "Low": 280.02,
        "Close": 280.02,
        "Volume": 100,
    }
    instance = StockCandlesHumanReadable(**data)
    assert isinstance(str(instance), str)


def test_stocks_candles_input_resolution_validation():

    valid_inputs = [
        "minutely",
        "1",
        "15M",
        "hourly",
        "H",
        "1H",
        "daily",
        "D",
        "1D",
        "weekly",
        "W",
        "1W",
        "monthly",
        "M",
        "1M",
        "yearly",
        "Y",
        "1Y",
        "1y",
        "1m",
    ]

    invalid_inputs = [
        "M1",
        "Random",
        "1x5",
        "15x",
        "15x5",
        "15x5M",
        "15x5H",
        "15x5D",
        "15x5W",
        "15x5M",
        "15x5y",
    ]

    for _input in valid_inputs:
        assert StocksCandlesInput(symbol="AAPL", resolution=_input).resolution == _input

    for _input in invalid_inputs:
        with pytest.raises(ValueError):
            StocksCandlesInput(symbol="AAPL", resolution=_input)


def test_get_stocks_candles_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
    )
    assert len(candles) == 253
    assert candles[0].t == datetime.datetime.fromtimestamp(1577941200, tz=pytz.timezone('US/Eastern'))
    assert candles[0].o == 74.06
    assert candles[0].h == 75.15
    assert candles[0].l == 73.7975
    assert candles[0].c == 75.0875
    assert candles[0].v == 135647456


def test_get_stocks_candles_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    candles = client.stocks.candles(
        symbol="AAPL", resolution="D", output_format=OutputFormat.JSON
    )
    mock_data.pop("s")
    assert candles == mock_data


def test_get_stocks_candles_response_200_internal_human_readable(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
        use_human_readable=True,
    )
    assert len(candles) == 253
    assert candles[0].Date == datetime.datetime.fromtimestamp(1577941200, tz=pytz.timezone('US/Eastern'))
    assert candles[0].Open == 74.06
    assert candles[0].High == 75.15
    assert candles[0].Low == 73.7975
    assert candles[0].Close == 75.0875
    assert candles[0].Volume == 135647456


def test_get_stocks_candles_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("stocks_candles_response_200")

        respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )

        candles = client.stocks.candles(
            symbol="AAPL",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
        )
        assert len(candles) == 253
        assert candles.index[0] == 1577941200
        assert candles.o.tolist()[0] == 74.06
        assert candles.h.tolist()[0] == 75.15
        assert candles.l.tolist()[0] == 73.7975
        assert candles.c.tolist()[0] == 75.0875
        assert candles.v.tolist()[0] == 135647456


def test_get_stocks_candles_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("stocks_candles_response_200")

        respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )
        candles = client.stocks.candles(
            symbol="AAPL",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
        )
        assert len(candles) == 253
        assert candles["t"][0] == 1577941200
        assert candles["o"][0] == 74.06
        assert candles["h"][0] == 75.15
        assert candles["l"][0] == 73.7975
        assert candles["c"][0] == 75.0875
        assert candles["v"][0] == 135647456


def test_get_stocks_candles_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )

    result = client.stocks.candles(symbol="AAPL", resolution="D")
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "Request failed with: Test error message"


def test_get_stocks_candles_response_200_dataframe_multiple_years_hourly(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/H/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="H",
        from_date=datetime.datetime(2020, 1, 1, tzinfo=pytz.timezone('US/Eastern')),
        to_date=datetime.datetime(2022, 10, 1, tzinfo=pytz.timezone('US/Eastern')),
        output_format=OutputFormat.DATAFRAME,
    )

    assert len(candles) == 253 * 3

    def _validate_candle(index: int, candle: StockCandle):
        assert candles.index[index] == 1577941200
        assert candles.o.tolist()[index] == 74.06
        assert candles.h.tolist()[index] == 75.15
        assert candles.l.tolist()[index] == 73.7975
        assert candles.c.tolist()[index] == 75.0875
        assert candles.v.tolist()[index] == 135647456

    _validate_candle(0, candles.iloc[0])

    second_year_first_candle = 253
    _validate_candle(second_year_first_candle, candles.iloc[second_year_first_candle])

    third_year_first_candle = 253 * 2
    _validate_candle(third_year_first_candle, candles.iloc[third_year_first_candle])


def test_get_stocks_candles_response_200_dataframe_multiple_years_daily(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        from_date=datetime.datetime(2020, 1, 1, tzinfo=pytz.timezone('US/Eastern')),
        to_date=datetime.datetime(2022, 10, 1, tzinfo=pytz.timezone('US/Eastern')),
        output_format=OutputFormat.DATAFRAME,
    )

    assert len(candles) == 253
    assert candles.index[0] == 1577941200
    assert candles.o.tolist()[0] == 74.06
    assert candles.h.tolist()[0] == 75.15
    assert candles.l.tolist()[0] == 73.7975
    assert candles.c.tolist()[0] == 75.0875
    assert candles.v.tolist()[0] == 135647456


def test_get_stocks_candles_response_200_dataframe_multiple_years_daily_no_to_date(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        from_date=datetime.datetime(2020, 1, 1),
        output_format=OutputFormat.DATAFRAME,
    )

    assert len(candles) == 253
    assert respx_mock.calls.last.request.url.params.get("to") is None


def test_get_stocks_candles_response_200_dataframe_multiple_years_hourly_no_to_date(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/H/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    with freeze_time("2023-01-01"):
        candles = client.stocks.candles(
            symbol="AAPL",
            resolution="H",
            from_date=datetime.datetime(2020, 1, 10, tzinfo=pytz.timezone('US/Eastern')),
            output_format=OutputFormat.DATAFRAME,
        )

    assert len(candles) == 253 * 3
    assert respx_mock.calls.last.request.url.params.get("to") is not None


def test_get_stocks_candles_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/stocks/candles/"],
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

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json={},
        status_code=501,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(candles, MarketDataClientErrorResult)


def test_get_stocks_candles_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        output_format=OutputFormat.CSV,
        filename="test.csv",
    )
    assert pathlib.Path(output).read_text() is not ""
