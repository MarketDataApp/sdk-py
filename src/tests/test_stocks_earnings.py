import datetime
import pathlib
from unittest.mock import patch

import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.output_types.stocks_earnings import (
    StockEarnings,
    StockEarningsHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult


def test_stock_earnings_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = StockEarnings(
        s="ok",
        symbol=["AAPL"],
        fiscalYear=[2023],
        fiscalQuarter=[1],
        date=[timestamp],
        reportDate=[timestamp],
        reportTime=["after close"],
        currency=["USD"],
        reportedEPS=[1.88],
        estimatedEPS=[1.94],
        surpriseEPS=[-0.06],
        surpriseEPSpct=[-3.0928],
        updated=[timestamp],
    )
    assert isinstance(str(instance), str)


def test_stock_earnings_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = StockEarningsHumanReadable(
        Symbol=["AAPL"],
        Fiscal_Year=[2023],
        Fiscal_Quarter=[1],
        Date=[timestamp],
        Report_Date=[timestamp],
        Report_Time=["after close"],
        Currency=["USD"],
        Reported_EPS=[1.88],
        Estimated_EPS=[1.94],
        Surprise_EPS=[-0.06],
        Surprise_EPS_Percent=[-3.0928],
        Updated=[timestamp],
    )
    assert isinstance(str(instance), str)


def test_get_stocks_earnings_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("stocks_earnings_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/earnings/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    earnings = client.stocks.earnings(
        symbol="AAPL", output_format=OutputFormat.INTERNAL
    )
    assert earnings.symbol == ["AAPL", "AAPL"]
    assert earnings.fiscalYear == [2026, 2026]
    assert earnings.fiscalQuarter == [1, 2]
    assert earnings.date == [
        datetime.datetime.fromtimestamp(1767157200, tz=pytz.timezone('US/Eastern')),
        datetime.datetime.fromtimestamp(1774929600, tz=pytz.timezone('US/Eastern')),
    ]
    assert earnings.reportDate == [
        datetime.datetime.fromtimestamp(1769576400, tz=pytz.timezone('US/Eastern')),
        datetime.datetime.fromtimestamp(1777435200, tz=pytz.timezone('US/Eastern')),
    ]
    assert earnings.reportTime == ["after close", "before open"]
    assert earnings.currency == ["USD", None]
    assert earnings.reportedEPS == [None, None]
    assert earnings.estimatedEPS == [2.67, None]
    assert earnings.surpriseEPS == [None, None]
    assert earnings.surpriseEPSpct == [None, None]
    assert earnings.updated == [
        datetime.datetime.fromtimestamp(1765861200, tz=pytz.timezone('US/Eastern')),
        datetime.datetime.fromtimestamp(1765861200, tz=pytz.timezone('US/Eastern')),
    ]


def test_get_stocks_earnings_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("stocks_earnings_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/earnings/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    earnings = client.stocks.earnings(symbol="AAPL", output_format=OutputFormat.JSON)
    assert earnings == mock_data


def test_get_stocks_earnings_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("stocks_earnings_human_response_200")
    respx_mock.get("https://api.marketdata.app/v1/stocks/earnings/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    earnings = client.stocks.earnings(
        symbol="AAPL", output_format=OutputFormat.INTERNAL, use_human_readable=True
    )
    assert earnings.Symbol == ["AAPL", "AAPL"]
    assert earnings.Fiscal_Year == [2026, 2026]
    assert earnings.Fiscal_Quarter == [1, 2]
    assert earnings.Date == [
        datetime.datetime.fromtimestamp(1767157200, tz=pytz.timezone('US/Eastern')),
        datetime.datetime.fromtimestamp(1774929600, tz=pytz.timezone('US/Eastern')),
    ]
    assert earnings.Report_Date == [
        datetime.datetime.fromtimestamp(1769576400, tz=pytz.timezone('US/Eastern')),
        datetime.datetime.fromtimestamp(1777435200, tz=pytz.timezone('US/Eastern')),
    ]
    assert earnings.Report_Time == ["after close", "before open"]
    assert earnings.Currency == ["USD", None]
    assert earnings.Reported_EPS == [None, None]
    assert earnings.Estimated_EPS == [2.67, None]
    assert earnings.Surprise_EPS == [None, None]
    assert earnings.Surprise_EPS_Percent == [None, None]
    assert earnings.Updated == [
        datetime.datetime.fromtimestamp(1765861200, tz=pytz.timezone('US/Eastern')),
        datetime.datetime.fromtimestamp(1765861200, tz=pytz.timezone('US/Eastern')),
    ]


def test_get_stocks_earnings_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("stocks_earnings_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/earnings/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )
        earnings = client.stocks.earnings(
            symbol="AAPL", output_format=OutputFormat.DATAFRAME
        )
        assert earnings.index.tolist() == ["AAPL", "AAPL"]
        assert earnings["fiscalYear"].tolist() == [2026, 2026]
        assert earnings["fiscalQuarter"].tolist() == [1, 2]
        assert earnings["date"].tolist() == [1767157200, 1774929600]
        assert earnings["reportDate"].tolist() == [1769576400, 1777435200]
        assert earnings["reportTime"].tolist() == ["after close", "before open"]
        assert earnings["currency"].tolist() == ["USD", None]
        assert earnings["reportedEPS"].tolist() == [None, None]
        assert earnings["surpriseEPS"].tolist() == [None, None]
        assert earnings["surpriseEPSpct"].tolist() == [None, None]
        assert earnings["updated"].tolist() == [1765861200, 1765861200]


def test_get_stocks_earnings_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("stocks_earnings_response_200")
        respx_mock.get("https://api.marketdata.app/v1/stocks/earnings/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )
        earnings = client.stocks.earnings(
            symbol="AAPL", output_format=OutputFormat.DATAFRAME
        )
        assert earnings["symbol"].to_list() == ["AAPL", "AAPL"]
        assert earnings["fiscalYear"].to_list() == [2026, 2026]
        assert earnings["fiscalQuarter"].to_list() == [1, 2]
        assert earnings["date"].to_list() == [1767157200, 1774929600]
        assert earnings["reportDate"].to_list() == [1769576400, 1777435200]
        assert earnings["reportTime"].to_list() == ["after close", "before open"]
        assert earnings["currency"].to_list() == ["USD", None]
        assert earnings["reportedEPS"].to_list() == [None, None]
        assert earnings["surpriseEPS"].to_list() == [None, None]
        assert earnings["surpriseEPSpct"].to_list() == [None, None]
        assert earnings["updated"].to_list() == [1765861200, 1765861200]


def test_get_stocks_earnings_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/earnings/AAPL/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )
    result = client.stocks.earnings(symbol="AAPL")
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "Request failed with: Test error message"


def test_get_stocks_earnings_status_offline(respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/stocks/earnings/"],
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
    respx_mock.get("https://api.marketdata.app/v1/stocks/earnings/AAPL/").respond(
        json={},
        status_code=501,
    )
    result = client.stocks.earnings(symbol="AAPL")
    assert isinstance(result, MarketDataClientErrorResult)


def test_get_stocks_earnings_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/earnings/AAPL/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.stocks.earnings(
        symbol="AAPL", output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
