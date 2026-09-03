"""Live tests for the markets resource: status."""

import datetime

from marketdata import MarketDataClient, OutputFormat
from marketdata.output_types.markets_status import MarketStatus


def _assert_market_status(entry: MarketStatus) -> None:
    assert isinstance(entry, MarketStatus), entry
    assert isinstance(entry.date, (datetime.date, datetime.datetime))
    assert entry.status in {"open", "closed"}


def test_status_defaults_to_today(live_client: MarketDataClient):
    statuses = live_client.markets.status(output_format=OutputFormat.INTERNAL)

    assert isinstance(statuses, list), statuses
    assert len(statuses) == 1
    _assert_market_status(statuses[0])


def test_status_returns_recent_trading_days(live_client: MarketDataClient):
    statuses = live_client.markets.status(
        countback=5, output_format=OutputFormat.INTERNAL
    )

    assert isinstance(statuses, list), statuses
    # countback counts dates before `to`; the API may include `to` itself, so
    # only the lower bound is a contract.
    assert len(statuses) >= 5
    for entry in statuses:
        _assert_market_status(entry)
    dates = [entry.date for entry in statuses]
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)
