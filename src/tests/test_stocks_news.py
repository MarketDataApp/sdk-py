import datetime
import pathlib
from unittest.mock import patch

import pytest
import pytz

from marketdata.exceptions import ServerError
from marketdata.input_types.base import DateFormat, OutputFormat
from marketdata.output_types.stocks_news import StockNews, StockNewsHumanReadable
from src.tests.conftest import assert_failed_answer, load_api_status


def test_stock_news_str():
    timestamp = int(
        datetime.datetime(
            2025, 1, 1, 0, 0, 0, 0, pytz.timezone("US/Eastern")
        ).timestamp()
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
        datetime.datetime(
            2025, 1, 1, 0, 0, 0, 0, pytz.timezone("US/Eastern")
        ).timestamp()
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
    assert news[0].publicationDate == datetime.datetime.fromtimestamp(
        1766120400, tz=pytz.timezone("US/Eastern")
    )
    assert news[0].updated == datetime.datetime.fromtimestamp(
        1766120400, tz=pytz.timezone("US/Eastern")
    )


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
    assert news[0].publicationDate == datetime.datetime.fromtimestamp(
        1766120400, tz=pytz.timezone("US/Eastern")
    )
    assert news[0].Date == datetime.datetime.fromtimestamp(
        1766120400, tz=pytz.timezone("US/Eastern")
    )


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
        assert news.publicationDate.tolist()[0] == datetime.datetime.fromtimestamp(
            1766120400, tz=pytz.timezone("US/Eastern")
        )
        assert news.updated.tolist()[0] == datetime.datetime.fromtimestamp(
            1766120400, tz=pytz.timezone("US/Eastern")
        )


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
        assert news["publicationDate"].to_list()[0] == datetime.datetime.fromtimestamp(
            1766120400, tz=pytz.timezone("US/Eastern")
        )
        assert news["updated"].to_list()[0] == datetime.datetime.fromtimestamp(
            1766120400, tz=pytz.timezone("US/Eastern")
        )


def test_get_stocks_news_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )
    with pytest.raises(ServerError) as exc_info:
        client.stocks.news(symbol="AAPL", output_format=OutputFormat.INTERNAL)
    assert exc_info.value.message == "Test error message"


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
    load_api_status(client)
    route = respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json={},
        status_code=501,
    )
    with pytest.raises(ServerError) as exc_info:
        client.stocks.news(symbol="AAPL", output_format=OutputFormat.INTERNAL)
    assert route.call_count == 1
    assert_failed_answer(
        exc_info.value, 501, "https://api.marketdata.app/v1/stocks/news/AAPL/", "{}"
    )


def test_get_stocks_news_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.stocks.news(
        symbol="AAPL", output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"


def _timestamp_news(load_json) -> tuple[dict, datetime.datetime]:
    """Build a news answer the way the API writes it under `dateformat=timestamp`.

    Returns:
        The answer, with a datetime with its offset in `publicationDate` and a
        date in `updated`, and the US/Eastern datetime both come from.
    """
    body = load_json("stocks_news_response_200")
    moment = datetime.datetime.fromtimestamp(
        body["publicationDate"][0], tz=pytz.timezone("US/Eastern")
    )
    text = moment.strftime("%Y-%m-%d %H:%M:%S %z")
    body = {
        "s": "ok",
        "symbol": body["symbol"][:2],
        "headline": body["headline"][:2],
        "content": body["content"][:2],
        "source": body["source"][:2],
        "publicationDate": [f"{text[:-2]}:{text[-2:]}"] * 2,
        "updated": moment.strftime("%Y-%m-%d"),
    }
    return body, moment


@pytest.mark.parametrize("handler", ["pandas", "polars"])
def test_news_dataframe_reads_timestamp_dates_as_us_eastern(
    load_json, respx_mock, client, handler
):
    """Under `dateformat=timestamp` a datetime and a date read back as the
    US/Eastern datetimes the default format gives, a date as its midnight."""
    body, moment = _timestamp_news(load_json)
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json=body, status_code=200
    )

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", [handler]):
        news = client.stocks.news(
            symbol="AAPL",
            output_format=OutputFormat.DATAFRAME,
            date_format=DateFormat.TIMESTAMP,
        )

    midnight = pytz.timezone("US/Eastern").localize(
        datetime.datetime.combine(moment.date(), datetime.time())
    )
    assert list(news["publicationDate"]) == [moment, moment]
    assert list(news["updated"]) == [midnight, midnight]


def test_news_internal_reads_timestamp_dates(load_json, respx_mock, client):
    """The models read the same answer to the same moment, and a date to the
    midnight of that day."""
    body, moment = _timestamp_news(load_json)
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json=body, status_code=200
    )

    news = client.stocks.news(
        symbol="AAPL",
        output_format=OutputFormat.INTERNAL,
        date_format=DateFormat.TIMESTAMP,
    )

    assert [item.publicationDate for item in news] == [moment, moment]
    for item in news:
        assert (item.updated.date(), item.updated.time()) == (
            moment.date(),
            datetime.time(),
        )


def test_news_json_keeps_timestamp_dates_as_sent(load_json, respx_mock, client):
    """JSON output is the API's answer: the dates stay the strings it sent."""
    body, _ = _timestamp_news(load_json)
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        json=body, status_code=200
    )

    news = client.stocks.news(
        symbol="AAPL",
        output_format=OutputFormat.JSON,
        date_format=DateFormat.TIMESTAMP,
    )

    assert news["publicationDate"] == body["publicationDate"]
    assert news["updated"] == body["updated"]


def test_news_csv_keeps_timestamp_dates_as_sent(
    load_json, respx_mock, client, tmp_path
):
    """CSV output is the API's body: the dates stay the text it sent."""
    body, _ = _timestamp_news(load_json)
    csv_body = (
        "symbol,publicationDate,updated\r\n"
        f"AAPL,{body['publicationDate'][0]},{body['updated']}\r\n"
    )
    respx_mock.get("https://api.marketdata.app/v1/stocks/news/AAPL/").respond(
        text=csv_body, status_code=200
    )

    path = client.stocks.news(
        symbol="AAPL",
        output_format=OutputFormat.CSV,
        date_format=DateFormat.TIMESTAMP,
        filename=tmp_path / "news.csv",
    )

    assert pathlib.Path(path).read_bytes() == csv_body.encode()
