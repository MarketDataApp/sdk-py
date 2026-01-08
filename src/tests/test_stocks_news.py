import datetime
import pathlib
from unittest.mock import patch

import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.output_types.stocks_news import StockNews, StockNewsHumanReadable
from marketdata.sdk_error import MarketDataClientErrorResult


def test_stock_news_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = StockNews(
        symbol="AAPL",
        headline="AAPL news",
        content="AAPL content",
        source="AAPL source",
        publicationDate=timestamp,
        updated=timestamp,
    )
    assert isinstance(str(instance), str)


def test_stock_news_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = StockNewsHumanReadable(
        Symbol="AAPL",
        headline="AAPL news",
        content="AAPL content",
        source="AAPL source",
        publicationDate=timestamp,
        Date=timestamp,
    )
    assert isinstance(str(instance), str)


def test_get_stocks_news_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("stocks_news_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    news = client.stocks.news(symbol="AAPL", output_format=OutputFormat.INTERNAL)
    assert news[0].symbol == "AAPL"
    assert news[0].headline.startswith("The top 10")
    assert news[0].content.startswith(
        "Nvidia (NVDA), Tesla (TSLA), and Palantir (PLTR)"
    )
    assert (
        news[0].source
        == "https://finance.yahoo.com/video/top-10-trending-tickers-2025-110024376.html"
    )
    assert news[0].publicationDate == datetime.datetime.fromtimestamp(1766120400, tz=pytz.timezone('US/Eastern'))
    assert news[0].updated == datetime.datetime.fromtimestamp(1766120400, tz=pytz.timezone('US/Eastern'))


def test_get_stocks_news_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("stocks_news_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    news = client.stocks.news(symbol="AAPL", output_format=OutputFormat.JSON)
    assert news == mock_data


def test_get_stocks_news_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("stocks_news_human_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    news = client.stocks.news(
        symbol="AAPL", output_format=OutputFormat.INTERNAL, use_human_readable=True
    )
    assert news[0].Symbol == "AAPL"
    assert news[0].headline.startswith("The top 10")
    assert news[0].content.startswith(
        "Nvidia (NVDA), Tesla (TSLA), and Palantir (PLTR)"
    )
    assert (
        news[0].source
        == "https://finance.yahoo.com/video/top-10-trending-tickers-2025-110024376.html"
    )
    assert news[0].publicationDate == datetime.datetime.fromtimestamp(1766120400, tz=pytz.timezone('US/Eastern'))
    assert news[0].Date == datetime.datetime.fromtimestamp(1766120400, tz=pytz.timezone('US/Eastern'))


def test_get_stocks_news_response_200_dataframe_pandas(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("stocks_news_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )
        news = client.stocks.news(symbol="AAPL", output_format=OutputFormat.DATAFRAME)
        assert len(news) == 1840
        assert news.index[0] == "AAPL"
        assert news.headline.tolist()[0].startswith("The top 10")
        assert news.content.tolist()[0].startswith(
            "Nvidia (NVDA), Tesla (TSLA), and Palantir (PLTR)"
        )
        assert (
            news.source.tolist()[0]
            == "https://finance.yahoo.com/video/top-10-trending-tickers-2025-110024376.html"
        )
        assert news.publicationDate.tolist()[0] == 1766120400
        assert news.updated.tolist()[0] == 1766120400


def test_get_stocks_news_response_200_dataframe_polars(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("stocks_news_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )
        news = client.stocks.news(symbol="AAPL", output_format=OutputFormat.DATAFRAME)
        assert len(news) == 1840
        assert news["symbol"].to_list() == ["AAPL"] * 1840
        assert news["headline"].to_list()[0].startswith("The top 10")
        assert (
            news["content"]
            .to_list()[0]
            .startswith("Nvidia (NVDA), Tesla (TSLA), and Palantir (PLTR)")
        )
        assert (
            news["source"].to_list()[0]
            == "https://finance.yahoo.com/video/top-10-trending-tickers-2025-110024376.html"
        )
        assert news["publicationDate"].to_list()[0] == 1766120400
        assert news["updated"].to_list()[0] == 1766120400


def test_get_stocks_news_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )
    news = client.stocks.news(symbol="AAPL", output_format=OutputFormat.INTERNAL)
    assert isinstance(news, MarketDataClientErrorResult)
    assert news.error.args[0] == "Request failed with: Test error message"


def test_get_stocks_news_status_offline(respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/stocks/news/"],
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
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json={},
        status_code=501,
    )
    news = client.stocks.news(symbol="AAPL", output_format=OutputFormat.INTERNAL)
    assert isinstance(news, MarketDataClientErrorResult)


def test_get_stocks_news_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.stocks.news(
        symbol="AAPL", output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
