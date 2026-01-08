import datetime
import pathlib
from unittest.mock import patch

import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.output_types.stocks_quotes import StockQuote, StockQuotesHumanReadable
from marketdata.sdk_error import MarketDataClientErrorResult


def test_stock_quote_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )

    instance = StockQuote(
        symbol="AAPL",
        ask=278.02,
        askSize=100,
        bid=277.97,
        bidSize=100,
        mid=277.995,
        last=278.0188,
        change=-0.0112,
        changepct=0.0,
        volume=4964676,
        updated=timestamp,
    )
    assert isinstance(str(instance), str)
    assert instance.change_percent == 0.0


def test_stock_quotes_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = StockQuotesHumanReadable(
        Symbol="AAPL",
        Ask=278.02,
        Ask_Size=100,
        Bid=277.97,
        Bid_Size=100,
        Mid=277.995,
        Last=278.0188,
        Change_Price=0.51,
        Change_Percent=0.0018,
        Volume=4964676,
        Date=timestamp,
    )
    assert isinstance(str(instance), str)


def test_stock_quote_post_init():
    data = {
        "symbol": "AAPL",
        "ask": 278.02,
        "askSize": 100,
        "bid": 277.97,
        "bidSize": 100,
        "mid": 277.995,
        "last": 278.0188,
        "change": -0.0112,
        "changepct": 0.0,
        "volume": 4964676,
        "updated": 1765478200,
    }
    instance = StockQuote(**data)
    instance.updated = 1765478200
    instance.__post_init__()
    assert instance.updated == datetime.datetime.fromtimestamp(1765478200, tz=pytz.timezone('US/Eastern'))


def test_stock_quote_from_dict():
    data = {
        "symbol": "AAPL",
        "ask": 278.02,
        "askSize": 100,
        "bid": 277.97,
        "bidSize": 100,
        "mid": 277.995,
        "last": 278.0188,
        "change": -0.0112,
        "changepct": 0.0,
        "volume": 4964676,
        "updated": 1765478200,
    }
    instance = StockQuote.from_dict(data)
    assert instance.symbol == "AAPL"
    assert instance.ask == 278.02
    assert instance.askSize == 100
    assert instance.bid == 277.97
    assert instance.bidSize == 100
    assert instance.mid == 277.995
    assert instance.last == 278.0188
    assert instance.change == -0.0112
    assert instance.changepct == 0.0
    assert instance.volume == 4964676
    assert instance.updated == datetime.datetime.fromtimestamp(1765478200, tz=pytz.timezone('US/Eastern'))


def test_stock_quotes_human_readable_str():
    data = {
        "Symbol": "AAPL",
        "Ask": 278.02,
        "Ask_Size": 100,
        "Bid": 277.97,
        "Bid_Size": 100,
        "Mid": 277.995,
        "Last": 278.0188,
        "Change_Price": 0.51,
        "Change_Percent": 0.0018,
        "Volume": 4964676,
        "Date": 1765478200,
    }
    instance = StockQuotesHumanReadable(**data)
    assert isinstance(str(instance), str)


def test_stock_quotes_human_readable_post_init():
    data = {
        "Symbol": "AAPL",
        "Ask": 278.02,
        "Ask_Size": 100,
        "Bid": 277.97,
        "Bid_Size": 100,
        "Mid": 277.995,
        "Last": 278.0188,
        "Change_Price": 0.51,
        "Change_Percent": 0.0018,
        "Volume": 4964676,
        "Date": 1765478200,
    }
    instance = StockQuotesHumanReadable(**data)
    instance.Date = 1765478200
    instance.__post_init__()
    assert instance.Date == datetime.datetime.fromtimestamp(1765478200, tz=pytz.timezone('US/Eastern'))


def test_stock_quotes_human_readable_from_dict():
    data = {
        "Symbol": "AAPL",
        "Ask": 278.02,
        "Ask Size": 100,
        "Bid": 277.97,
        "Bid Size": 100,
        "Mid": 277.995,
        "Last": 278.0188,
        "Change $": 0.51,
        "Change %": 0.0018,
        "Volume": 4964676,
        "Date": 1765478200,
    }
    instance = StockQuotesHumanReadable.from_dict(data)
    assert instance.Symbol == "AAPL"
    assert instance.Ask == 278.02
    assert instance.Ask_Size == 100
    assert instance.Bid == 277.97
    assert instance.Bid_Size == 100
    assert instance.Mid == 277.995
    assert instance.Last == 278.0188
    assert instance.Change_Price == 0.51
    assert instance.Change_Percent == 0.0018
    assert instance.Volume == 4964676
    assert instance.Date == datetime.datetime.fromtimestamp(1765478200, tz=pytz.timezone('US/Eastern'))


def test_get_stocks_quotes_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("stocks_quotes_response_200")
    updated = datetime.datetime.fromtimestamp(1765552906, tz=pytz.timezone('US/Eastern'))

    respx_mock.get("https://api.marketdata.app/v1/stocks/bulkquotes/").respond(
        json=mock_data,
        status_code=200,
    )

    quotes = client.stocks.quotes(
        symbols=["AAPL", "MSFT"],
        output_format=OutputFormat.INTERNAL,
    )
    assert len(quotes) == 2
    assert quotes[0].symbol == "AAPL"
    assert quotes[0].ask == 278.02
    assert quotes[0].askSize == 100
    assert quotes[0].bid == 277.97
    assert quotes[0].bidSize == 100
    assert quotes[0].mid == 277.995
    assert quotes[0].last == 278.0188
    assert quotes[0].change == -0.0112
    assert quotes[0].changepct == 0.0
    assert quotes[0].volume == 4964676
    assert quotes[0].updated == updated
    assert quotes[1].symbol == "MSFT"
    assert quotes[1].ask == 479.45
    assert quotes[1].askSize == 40
    assert quotes[1].bid == 479.37
    assert quotes[1].bidSize == 40
    assert quotes[1].mid == 479.41
    assert quotes[1].last == 479.42
    assert quotes[1].change == -4.05
    assert quotes[1].changepct == -0.0084
    assert quotes[1].volume == 3581398
    assert quotes[1].updated == updated


def test_get_stocks_quotes_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("stocks_quotes_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/bulkquotes/").respond(
        json=mock_data,
        status_code=200,
    )
    quotes = client.stocks.quotes(
        symbols=["AAPL", "MSFT"], output_format=OutputFormat.JSON
    )
    assert quotes == mock_data


def test_get_stocks_quotes_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("stocks_quotes_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/bulkquotes/").respond(
        json=mock_data,
        status_code=200,
    )
    quotes = client.stocks.quotes(
        symbols=["AAPL", "MSFT"],
        output_format=OutputFormat.INTERNAL,
        use_human_readable=True,
    )
    assert quotes[0].Symbol == "AAPL"
    assert quotes[0].Ask == 278.55
    assert quotes[0].Ask_Size == 400
    assert quotes[0].Bid == 278.54
    assert quotes[0].Bid_Size == 100
    assert quotes[0].Mid == 278.545
    assert quotes[0].Last == 278.54
    assert quotes[0].Change_Price == 0.51
    assert quotes[0].Change_Percent == 0.0018
    assert quotes[0].Volume == 17525589
    assert quotes[0].Date == datetime.datetime.fromtimestamp(1765565453, tz=pytz.timezone('US/Eastern'))


def test_get_stocks_quotes_response_200_dataframe_pandas(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("stocks_quotes_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/bulkquotes/").respond(
            json=mock_data,
            status_code=200,
        )

        quotes = client.stocks.quotes(
            symbols=["AAPL", "MSFT"],
            output_format=OutputFormat.DATAFRAME,
        )
        assert "s" not in quotes.columns
        assert len(quotes) == 2
        assert quotes.index.tolist() == ["AAPL", "MSFT"]
        assert quotes.ask.tolist() == [278.02, 479.45]
        assert quotes.askSize.tolist() == [100, 40]
        assert quotes.bid.tolist() == [277.97, 479.37]
        assert quotes.bidSize.tolist() == [100, 40]
        assert quotes.mid.tolist() == [277.995, 479.41]
        assert quotes.change.tolist() == [-0.0112, -4.05]
        assert quotes.changepct.tolist() == [0.0, -0.0084]
        assert quotes.volume.tolist() == [4964676, 3581398]
        assert quotes.updated.tolist() == [1765552906, 1765552906]


def test_get_stocks_quotes_response_200_dataframe_polars(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("stocks_quotes_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/bulkquotes/").respond(
            json=mock_data,
            status_code=200,
        )

        quotes = client.stocks.quotes(
            symbols=["AAPL", "MSFT"],
            output_format=OutputFormat.DATAFRAME,
        )
        assert "s" not in quotes.columns
        assert len(quotes) == 2
        assert quotes["symbol"].to_list() == ["AAPL", "MSFT"]
        assert quotes["ask"].to_list() == [278.02, 479.45]
        assert quotes["askSize"].to_list() == [100, 40]
        assert quotes["bid"].to_list() == [277.97, 479.37]
        assert quotes["bidSize"].to_list() == [100, 40]
        assert quotes["mid"].to_list() == [277.995, 479.41]
        assert quotes["change"].to_list() == [-0.0112, -4.05]
        assert quotes["changepct"].to_list() == [0.0, -0.0084]
        assert quotes["volume"].to_list() == [4964676, 3581398]
        assert quotes["updated"].to_list() == [1765552906, 1765552906]


def test_get_stocks_quotes_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/bulkquotes/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )

    result = client.stocks.quotes(
        symbols=["AAPL", "MSFT"],
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "Request failed with: Test error message"


def test_get_stocks_quotes_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/stocks/bulkquotes/"],
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

    respx_mock.get("https://api.marketdata.app/v1/stocks/bulkquotes/").respond(
        json={},
        status_code=501,
    )

    quotes = client.stocks.quotes(
        symbols=["AAPL", "MSFT"],
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(quotes, MarketDataClientErrorResult)


def test_get_stocks_quotes_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/bulkquotes/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.stocks.quotes(
        symbols=["AAPL", "MSFT"], output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
