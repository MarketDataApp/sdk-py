import copy
import datetime
import pathlib
from decimal import Decimal
from unittest.mock import patch

import pytest
import pytz

from marketdata.exceptions import ServerError
from marketdata.input_types.base import DateFormat, OutputFormat
from marketdata.output_types.stocks_quotes import StockQuote, StockQuotesHumanReadable
from src.tests.conftest import assert_failed_answer, load_api_status


def test_stock_quote_str():
    timestamp = int(
        datetime.datetime(
            2025, 1, 1, 0, 0, 0, 0, pytz.timezone("US/Eastern")
        ).timestamp()
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


def test_stock_quotes_human_readable_str_from_keywords():
    timestamp = int(
        datetime.datetime(
            2025, 1, 1, 0, 0, 0, 0, pytz.timezone("US/Eastern")
        ).timestamp()
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
    assert instance.updated == datetime.datetime.fromtimestamp(
        1765478200, tz=pytz.timezone("US/Eastern")
    )


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
    assert instance.ask == Decimal("278.02")
    assert instance.askSize == 100
    assert instance.bid == Decimal("277.97")
    assert instance.bidSize == 100
    assert instance.mid == Decimal("277.995")
    assert instance.last == Decimal("278.0188")
    assert instance.change == Decimal("-0.0112")
    assert instance.changepct == 0.0
    assert instance.volume == 4964676
    assert instance.updated == datetime.datetime.fromtimestamp(
        1765478200, tz=pytz.timezone("US/Eastern")
    )


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
    assert instance.Date == datetime.datetime.fromtimestamp(
        1765478200, tz=pytz.timezone("US/Eastern")
    )


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
    assert instance.Ask == Decimal("278.02")
    assert instance.Ask_Size == 100
    assert instance.Bid == Decimal("277.97")
    assert instance.Bid_Size == 100
    assert instance.Mid == Decimal("277.995")
    assert instance.Last == Decimal("278.0188")
    assert instance.Change_Price == Decimal("0.51")
    assert instance.Change_Percent == 0.0018
    assert instance.Volume == 4964676
    assert instance.Date == datetime.datetime.fromtimestamp(
        1765478200, tz=pytz.timezone("US/Eastern")
    )


def test_get_stocks_quotes_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("stocks_quotes_response_200")
    updated = datetime.datetime.fromtimestamp(
        1765552906, tz=pytz.timezone("US/Eastern")
    )

    respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        json=mock_data,
        status_code=200,
    )

    quotes = client.stocks.quotes(
        symbols=["AAPL", "MSFT"],
        output_format=OutputFormat.INTERNAL,
    )
    assert len(quotes) == 2
    assert quotes[0].symbol == "AAPL"
    assert quotes[0].ask == Decimal("278.02")
    assert quotes[0].askSize == 100
    assert quotes[0].bid == Decimal("277.97")
    assert quotes[0].bidSize == 100
    assert quotes[0].mid == Decimal("277.995")
    assert quotes[0].last == Decimal("278.0188")
    assert quotes[0].change == Decimal("-0.0112")
    assert quotes[0].changepct == 0.0
    assert quotes[0].volume == 4964676
    assert quotes[0].updated == updated
    assert quotes[1].symbol == "MSFT"
    assert quotes[1].ask == Decimal("479.45")
    assert quotes[1].askSize == 40
    assert quotes[1].bid == Decimal("479.37")
    assert quotes[1].bidSize == 40
    assert quotes[1].mid == Decimal("479.41")
    assert quotes[1].last == Decimal("479.42")
    assert quotes[1].change == Decimal("-4.05")
    assert quotes[1].changepct == -0.0084
    assert quotes[1].volume == 3581398
    assert quotes[1].updated == updated


def test_get_stocks_quotes_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("stocks_quotes_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        json=mock_data,
        status_code=200,
    )
    quotes = client.stocks.quotes(
        symbols=["AAPL", "MSFT"], output_format=OutputFormat.JSON
    )
    assert quotes == mock_data


def test_get_stocks_quotes_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("stocks_quotes_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        json=mock_data,
        status_code=200,
    )
    quotes = client.stocks.quotes(
        symbols=["AAPL", "MSFT"],
        output_format=OutputFormat.INTERNAL,
        use_human_readable=True,
    )
    assert quotes[0].Symbol == "AAPL"
    assert quotes[0].Ask == Decimal("278.55")
    assert quotes[0].Ask_Size == 400
    assert quotes[0].Bid == Decimal("278.54")
    assert quotes[0].Bid_Size == 100
    assert quotes[0].Mid == Decimal("278.545")
    assert quotes[0].Last == Decimal("278.54")
    assert quotes[0].Change_Price == Decimal("0.51")
    assert quotes[0].Change_Percent == 0.0018
    assert quotes[0].Volume == 17525589
    assert quotes[0].Date == datetime.datetime.fromtimestamp(
        1765565453, tz=pytz.timezone("US/Eastern")
    )


def test_get_stocks_quotes_response_200_dataframe_pandas(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("stocks_quotes_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
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
        expected_updated = [
            datetime.datetime.fromtimestamp(1765552906, tz=pytz.timezone("US/Eastern")),
            datetime.datetime.fromtimestamp(1765552906, tz=pytz.timezone("US/Eastern")),
        ]
        assert quotes.updated.tolist() == expected_updated


def test_get_stocks_quotes_response_200_dataframe_polars(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("stocks_quotes_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
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
        expected_updated = [
            datetime.datetime.fromtimestamp(1765552906, tz=pytz.timezone("US/Eastern")),
            datetime.datetime.fromtimestamp(1765552906, tz=pytz.timezone("US/Eastern")),
        ]
        assert quotes["updated"].to_list() == expected_updated


def _timestamp_text(timestamp: int) -> str:
    """Write a Unix time the way the API's ``dateformat=timestamp`` does."""
    moment = datetime.datetime.fromtimestamp(timestamp, tz=pytz.timezone("US/Eastern"))
    text = moment.strftime("%Y-%m-%d %H:%M:%S %z")
    return f"{text[:-2]}:{text[-2:]}"


def test_get_stocks_quotes_response_200_dataframe_pandas_timestamp_dateformat(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = copy.deepcopy(load_json("stocks_quotes_response_200"))
        updated_ts = mock_data["updated"][0]
        updated_iso = _timestamp_text(updated_ts)
        mock_data["updated"] = [updated_iso, updated_iso]
        respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
            json=mock_data,
            status_code=200,
        )

        quotes = client.stocks.quotes(
            symbols=["AAPL", "MSFT"],
            output_format=OutputFormat.DATAFRAME,
            date_format=DateFormat.TIMESTAMP,
        )
        expected_updated = [
            datetime.datetime.fromtimestamp(updated_ts, tz=pytz.timezone("US/Eastern")),
            datetime.datetime.fromtimestamp(updated_ts, tz=pytz.timezone("US/Eastern")),
        ]
        assert quotes.updated.tolist() == expected_updated


def test_get_stocks_quotes_response_200_dataframe_polars_timestamp_dateformat(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = copy.deepcopy(load_json("stocks_quotes_response_200"))
        updated_ts = mock_data["updated"][0]
        updated_iso = _timestamp_text(updated_ts)
        mock_data["updated"] = [updated_iso, updated_iso]
        respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
            json=mock_data,
            status_code=200,
        )

        quotes = client.stocks.quotes(
            symbols=["AAPL", "MSFT"],
            output_format=OutputFormat.DATAFRAME,
            date_format=DateFormat.TIMESTAMP,
        )
        expected_updated = [
            datetime.datetime.fromtimestamp(updated_ts, tz=pytz.timezone("US/Eastern")),
            datetime.datetime.fromtimestamp(updated_ts, tz=pytz.timezone("US/Eastern")),
        ]
        assert quotes["updated"].to_list() == expected_updated


def test_get_stocks_quotes_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )

    with pytest.raises(ServerError) as exc_info:
        client.stocks.quotes(
            symbols=["AAPL", "MSFT"],
            output_format=OutputFormat.INTERNAL,
        )
    assert exc_info.value.message == "Test error message"


def test_get_stocks_quotes_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/stocks/quotes/"],
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

    route = respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        json={},
        status_code=501,
    )

    with pytest.raises(ServerError) as exc_info:
        client.stocks.quotes(
            symbols=["AAPL", "MSFT"],
            output_format=OutputFormat.INTERNAL,
        )
    assert route.call_count == 1
    assert_failed_answer(
        exc_info.value, 501, "https://api.marketdata.app/v1/stocks/quotes/", "{}"
    )


def test_get_stocks_quotes_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.stocks.quotes(
        symbols=["AAPL", "MSFT"], output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"


def test_get_stocks_quotes_requests_the_quotes_endpoint(load_json, respx_mock, client):
    """#74: `stocks/bulkquotes/` is deprecated; `stocks/quotes/` takes
    `?symbols=A,B,C` at full parity and is what goes on the wire."""
    mock_data = load_json("stocks_quotes_response_200")
    route = respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        json=mock_data, status_code=200
    )

    client.stocks.quotes(["AAPL", "META"], output_format=OutputFormat.JSON)

    request = route.calls.last.request
    assert request.url.path == "/v1/stocks/quotes/"
    assert request.url.params["symbols"] == "AAPL,META"
    assert "bulkquotes" not in str(request.url)


# The 52-week keys of each answer, as the API names them, and the fields that
# hold them.
FIFTY_TWO_WEEK = [
    pytest.param(
        "stocks_quotes_response_200",
        False,
        ("52weekHigh", "52weekLow"),
        ("fiftyTwoWeekHigh", "fiftyTwoWeekLow"),
        id="plain",
    ),
    pytest.param(
        "stocks_quotes_human_response_200",
        True,
        ("52 Week High", "52 Week Low"),
        ("Fifty_Two_Week_High", "Fifty_Two_Week_Low"),
        id="human",
    ),
]


@pytest.mark.parametrize(("fixture", "human", "keys", "fields"), FIFTY_TWO_WEEK)
def test_internal_quotes_carry_the_52_week_range_when_asked_for(
    load_json, respx_mock, client, fixture, human, keys, fields
):
    """The 52-week keys, which no field can be named after, fill their own
    fields as money, a whole-number price included."""
    body = load_json(fixture)
    rows = len(body["Symbol" if human else "symbol"])
    body[keys[0]] = [288.62] * rows
    body[keys[1]] = [169] * rows
    route = respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        json=body, status_code=200
    )

    quotes = client.stocks.quotes(
        "AAPL",
        use_52_week=True,
        use_human_readable=human,
        output_format=OutputFormat.INTERNAL,
    )

    assert route.calls.last.request.url.params["52week"] == "true"
    assert len(quotes) == rows
    for quote in quotes:
        high, low = (getattr(quote, field) for field in fields)
        assert isinstance(high, Decimal) and high == Decimal("288.62")
        assert isinstance(low, Decimal) and low == Decimal("169")


@pytest.mark.parametrize(("fixture", "human", "keys", "fields"), FIFTY_TWO_WEEK)
def test_internal_quotes_hold_no_52_week_range_when_not_asked_for(
    load_json, respx_mock, client, fixture, human, keys, fields
):
    """Without ``use_52_week`` the answer has no 52-week keys and the fields
    are ``None``."""
    respx_mock.get("https://api.marketdata.app/v1/stocks/quotes/").respond(
        json=load_json(fixture), status_code=200
    )

    quotes = client.stocks.quotes(
        "AAPL", use_human_readable=human, output_format=OutputFormat.INTERNAL
    )

    assert quotes
    for quote in quotes:
        assert [getattr(quote, field) for field in fields] == [None, None]
