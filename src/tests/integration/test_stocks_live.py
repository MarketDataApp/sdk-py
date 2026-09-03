"""Live tests for the stocks resource: prices, quotes, candles, earnings, news."""

import datetime

from marketdata import MarketDataClient, MarketDataClientErrorResult, OutputFormat
from marketdata.output_types.stocks_candles import StockCandle
from marketdata.output_types.stocks_earnings import StockEarnings
from marketdata.output_types.stocks_news import StockNews
from marketdata.output_types.stocks_prices import StockPrice
from marketdata.output_types.stocks_quotes import StockQuote

SYMBOL = "AAPL"

EARNINGS_LIST_FIELDS = (
    "fiscalYear",
    "fiscalQuarter",
    "date",
    "reportDate",
    "reportTime",
    "currency",
    "reportedEPS",
    "estimatedEPS",
    "surpriseEPS",
    "surpriseEPSpct",
    "updated",
)


def _last_weekend() -> tuple[datetime.date, datetime.date]:
    today = datetime.date.today()
    days_since_saturday = (today.weekday() + 2) % 7 or 7
    saturday = today - datetime.timedelta(days=days_since_saturday)
    return saturday, saturday + datetime.timedelta(days=1)


def test_prices_return_expected_shape(live_client: MarketDataClient):
    prices = live_client.stocks.prices(SYMBOL, output_format=OutputFormat.INTERNAL)

    assert isinstance(prices, list), prices
    assert len(prices) == 1
    price = prices[0]
    assert isinstance(price, StockPrice)
    assert price.symbol == SYMBOL
    assert price.mid > 0
    assert isinstance(price.change, float)
    assert isinstance(price.changepct, float)
    assert isinstance(price.updated, datetime.datetime)
    assert price.updated.tzinfo is not None


def test_quotes_return_expected_shape(live_client: MarketDataClient):
    quotes = live_client.stocks.quotes(SYMBOL, output_format=OutputFormat.INTERNAL)

    assert isinstance(quotes, list), quotes
    assert len(quotes) == 1
    quote = quotes[0]
    assert isinstance(quote, StockQuote)
    assert quote.symbol == SYMBOL
    assert quote.last > 0
    # Outside market hours bid/ask can be 0, so only their ordering is a contract.
    assert 0 <= quote.bid <= quote.ask
    assert quote.mid >= 0
    assert isinstance(quote.bidSize, int) and quote.bidSize >= 0
    assert isinstance(quote.askSize, int) and quote.askSize >= 0
    assert isinstance(quote.volume, int) and quote.volume >= 0
    assert isinstance(quote.updated, datetime.datetime)


def test_daily_candles_return_expected_shape(live_client: MarketDataClient):
    candles = live_client.stocks.candles(
        SYMBOL, resolution="D", countback=5, output_format=OutputFormat.INTERNAL
    )

    assert isinstance(candles, list), candles
    assert len(candles) == 5
    assert all(isinstance(candle, StockCandle) for candle in candles)

    stamps = [candle.t for candle in candles]
    assert all(isinstance(stamp, datetime.datetime) for stamp in stamps)
    assert stamps == sorted(stamps)
    assert len(set(stamps)) == len(stamps)
    for candle in candles:
        assert candle.l > 0
        assert candle.l <= candle.o <= candle.h
        assert candle.l <= candle.c <= candle.h
        assert isinstance(candle.v, int) and candle.v > 0


def test_long_intraday_range_has_no_duplicate_bars_at_chunk_boundaries(
    live_client: MarketDataClient,
):
    """Live witness for #51: an intraday range longer than a year is fetched
    in year-sized chunks. The API treats a date-only `to=` as inclusive, so
    chunks that shared their boundary day returned that day twice."""
    today = datetime.date.today()

    candles = live_client.stocks.candles(
        SYMBOL,
        resolution="H",
        from_date=today - datetime.timedelta(days=400),
        to_date=today,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(candles, list), candles
    stamps = [candle.t for candle in candles]
    # Roughly seven hourly bars per session over 250+ sessions.
    assert len(stamps) > 1000
    assert len(set(stamps)) == len(stamps), "duplicate bars at a chunk boundary"
    assert stamps == sorted(stamps)


def test_earnings_return_expected_shape(live_client: MarketDataClient):
    earnings = live_client.stocks.earnings(
        SYMBOL, countback=4, output_format=OutputFormat.INTERNAL
    )

    assert isinstance(earnings, StockEarnings), earnings
    assert earnings.s == "ok"
    reports = len(earnings.symbol)
    assert reports >= 1

    # Column-oriented payload: every field is a list of the same length.
    for field in EARNINGS_LIST_FIELDS:
        assert len(getattr(earnings, field)) == reports, field

    assert set(earnings.symbol) == {SYMBOL}
    assert all(isinstance(year, int) and year >= 2000 for year in earnings.fiscalYear)
    assert all(quarter in (1, 2, 3, 4) for quarter in earnings.fiscalQuarter)
    assert all(isinstance(day, datetime.datetime) for day in earnings.reportDate)
    assert all(isinstance(day, datetime.datetime) for day in earnings.updated)


def test_news_return_expected_shape(live_client: MarketDataClient):
    news = live_client.stocks.news(
        SYMBOL, countback=1, output_format=OutputFormat.INTERNAL
    )

    assert isinstance(news, list), news
    assert len(news) == 1
    item = news[0]
    assert isinstance(item, StockNews)
    assert item.symbol == SYMBOL
    assert item.headline.strip()
    assert item.source.strip()
    assert isinstance(item.publicationDate, datetime.datetime)
    assert isinstance(item.updated, datetime.datetime)


def test_no_data_answer_is_a_404_no_data_result(live_client: MarketDataClient):
    """A valid question with an empty answer (daily candles over a weekend)
    comes back as HTTP 404 with `s: "no_data"`. In v1 that surfaces as an
    error result carrying the status; #62 turns it into an empty result."""
    saturday, sunday = _last_weekend()

    result = live_client.stocks.candles(
        SYMBOL,
        resolution="D",
        from_date=saturday,
        to_date=sunday,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(result, MarketDataClientErrorResult), result
    assert result.error.status_code == 404
    assert "no_data" in result.error.message
