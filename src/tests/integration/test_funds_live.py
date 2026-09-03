"""Live test for the funds resource: candles."""

import datetime

from marketdata import MarketDataClient, OutputFormat
from marketdata.output_types.funds_candles import FundsCandle

FUND = "VFINX"


def test_candles_return_recent_fund_prices(live_client: MarketDataClient):
    candles = live_client.funds.candles(
        FUND, countback=5, output_format=OutputFormat.INTERNAL
    )

    assert isinstance(candles, list), candles
    assert len(candles) == 5
    assert all(isinstance(candle, FundsCandle) for candle in candles)

    stamps = [candle.t for candle in candles]
    assert all(isinstance(stamp, datetime.datetime) for stamp in stamps)
    assert stamps == sorted(stamps)
    assert len(set(stamps)) == len(stamps)
    for candle in candles:
        assert candle.l > 0
        assert candle.l <= candle.o <= candle.h
        assert candle.l <= candle.c <= candle.h
