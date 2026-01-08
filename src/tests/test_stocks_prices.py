import datetime
import pathlib
from unittest.mock import patch

import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.output_types.stocks_prices import StockPrice, StockPricesHumanReadable
from marketdata.sdk_error import MarketDataClientErrorResult


def test_stock_price_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )

    instance = StockPrice(
        s="ok",
        symbol="AAPL",
        mid=280.02,
        change=-0.68,
        changepct=-0.0024,
        updated=timestamp,
    )

    assert isinstance(str(instance), str)


def test_stock_prices_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    data = {
        "Symbol": "AAPL",
        "Mid": 280.02,
        "Change_Price": -0.68,
        "Change_Percent": -0.0024,
        "Date": timestamp,
    }
    instance = StockPricesHumanReadable(**data)
    assert isinstance(str(instance), str)


def test_get_stocks_prices_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("stocks_prices_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json=mock_data,
        status_code=200,
    )

    prices = client.stocks.prices(
        symbols=["AAPL", "TSLA"],
        output_format=OutputFormat.INTERNAL,
    )

    symbols = [price.symbol for price in prices]
    assert symbols == ["AAPL", "TSLA"]

    mids = [price.mid for price in prices]
    assert mids == [280.02, 455.76]

    changes = [price.change for price in prices]
    assert changes == [-0.68, 1.23]

    changepcts = [price.changepct for price in prices]
    assert changepcts == [-0.0024, 0.0027]

    updateds = [price.updated for price in prices]
    # API returns UTC, convert to US/Eastern for comparison
    expected = [
        datetime.datetime(2025, 12, 5, 16, 2, 26, tzinfo=datetime.timezone.utc).astimezone(pytz.timezone('US/Eastern')),
        datetime.datetime(2025, 12, 5, 16, 2, 20, tzinfo=datetime.timezone.utc).astimezone(pytz.timezone('US/Eastern')),
    ]
    assert [dt.astimezone(pytz.timezone('US/Eastern')) for dt in updateds] == expected


def test_get_stocks_prices_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("stocks_prices_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json=mock_data,
        status_code=200,
    )
    prices = client.stocks.prices(symbols="TSLA", output_format=OutputFormat.JSON)
    assert prices == mock_data


def test_get_stocks_prices_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("stocks_prices_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json=mock_data,
        status_code=200,
    )
    prices = client.stocks.prices(
        symbols="TSLA", output_format=OutputFormat.INTERNAL, use_human_readable=True
    )
    symbols = [price.Symbol for price in prices]
    assert symbols == ["AAPL", "TSLA"]
    mids = [price.Mid for price in prices]
    assert mids == [278.72, 455.66]
    changes = [price.Change_Price for price in prices]
    assert changes == [0.69, 8.77]
    changepcts = [price.Change_Percent for price in prices]
    assert changepcts == [0.0025, 0.0196]
    updateds = [price.Date for price in prices]
    assert updateds == [
        datetime.datetime.fromtimestamp(1765564415, tz=pytz.timezone('US/Eastern')),
        datetime.datetime.fromtimestamp(1765564416, tz=pytz.timezone('US/Eastern')),
    ]


def test_get_stocks_prices_response_200_dataframe_pandas(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("stocks_prices_response_200")

        respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
            json=mock_data,
            status_code=200,
        )

        prices = client.stocks.prices(
            symbols="TSLA", output_format=OutputFormat.DATAFRAME
        )
        assert "s" not in prices.columns
        assert len(prices) == 2
        assert prices.index.tolist() == ["AAPL", "TSLA"]
        assert prices["mid"].tolist() == [280.02, 455.76]
        assert prices["change"].tolist() == [-0.68, 1.23]
        assert prices["changepct"].tolist() == [-0.0024, 0.0027]
        assert prices["updated"].tolist() == [1764950546, 1764950540]


def test_get_stocks_prices_response_200_dataframe_polars(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("stocks_prices_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
            json=mock_data,
            status_code=200,
        )
        prices = client.stocks.prices(
            symbols="TSLA", output_format=OutputFormat.DATAFRAME
        )
        assert "s" not in prices.columns
        assert len(prices) == 2
        assert prices["symbol"].to_list() == ["AAPL", "TSLA"]
        assert prices["mid"].to_list() == [280.02, 455.76]
        assert prices["change"].to_list() == [-0.68, 1.23]
        assert prices["changepct"].to_list() == [-0.0024, 0.0027]
        assert prices["updated"].to_list() == [1764950546, 1764950540]


def test_get_stocks_prices_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )

    result = client.stocks.prices(symbols="TSLA", output_format=OutputFormat.INTERNAL)
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "Request failed with: Test error message"


def test_get_stocks_prices_status_offline(respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/stocks/prices/"],
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

    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        json={},
        status_code=501,
    )

    prices = client.stocks.prices(symbols="TSLA", output_format=OutputFormat.INTERNAL)
    assert isinstance(prices, MarketDataClientErrorResult)


def test_get_stocks_prices_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/prices/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.stocks.prices(
        symbols="TSLA", output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
