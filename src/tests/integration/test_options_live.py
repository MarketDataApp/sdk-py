"""Live tests for the options resource: chain, expirations, quotes, lookup."""

import datetime
from decimal import Decimal

import pytest

from marketdata import MarketDataClient, OutputFormat
from marketdata.output_types.options_chain import OptionsChain
from marketdata.output_types.options_expirations import OptionsExpirations
from marketdata.output_types.options_lookup import OptionsLookup
from marketdata.output_types.options_quotes import OptionsQuotes

UNDERLYING = "AAPL"

CHAIN_LIST_FIELDS = (
    "optionSymbol",
    "underlying",
    "expiration",
    "side",
    "strike",
    "firstTraded",
    "dte",
    "updated",
    "bid",
    "bidSize",
    "mid",
    "ask",
    "askSize",
    "last",
    "openInterest",
    "volume",
    "inTheMoney",
    "intrinsicValue",
    "extrinsicValue",
    "underlyingPrice",
    "iv",
    "delta",
    "gamma",
    "theta",
    "vega",
)


@pytest.fixture(scope="module")
def live_chain(live_client: MarketDataClient) -> OptionsChain:
    # A tightly filtered chain (about 30 days out, two strikes around the
    # money) keeps the payload small; the same contracts feed the quotes and
    # lookup tests below.
    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=30,
        strike_limit=2,
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(chain, OptionsChain), chain
    return chain


def test_expirations_return_future_dates(live_client: MarketDataClient):
    expirations = live_client.options.expirations(
        UNDERLYING, output_format=OutputFormat.INTERNAL
    )

    assert isinstance(expirations, OptionsExpirations), expirations
    assert expirations.s == "ok"
    assert len(expirations.expirations) >= 1
    assert all(isinstance(e, datetime.datetime) for e in expirations.expirations)
    assert expirations.expirations == sorted(expirations.expirations)
    assert expirations.expirations[-1].date() >= datetime.date.today()
    assert isinstance(expirations.updated, datetime.datetime)


def test_chain_returns_expected_shape(live_chain: OptionsChain):
    assert live_chain.s == "ok"
    contracts = len(live_chain.optionSymbol)
    assert contracts >= 1

    # Column-oriented payload: every field is a list of the same length.
    for field in CHAIN_LIST_FIELDS:
        assert len(getattr(live_chain, field)) == contracts, field

    assert all(symbol.startswith(UNDERLYING) for symbol in live_chain.optionSymbol)
    assert set(live_chain.underlying) == {UNDERLYING}
    assert set(live_chain.side) <= {"call", "put"}
    assert all(strike > 0 for strike in live_chain.strike)
    assert all(isinstance(e, datetime.datetime) for e in live_chain.expiration)
    assert all(isinstance(dte, int) and dte >= 0 for dte in live_chain.dte)
    assert all(price > 0 for price in live_chain.underlyingPrice)
    # Money is exact (#50); the greeks and IV stay floats.
    for field in ("strike", "underlyingPrice"):
        assert all(isinstance(v, Decimal) for v in getattr(live_chain, field))
    for field in ("iv", "delta", "gamma", "theta", "vega"):
        assert not any(isinstance(v, Decimal) for v in getattr(live_chain, field))


def test_quotes_return_expected_shape(
    live_client: MarketDataClient, live_chain: OptionsChain
):
    option_symbol = live_chain.optionSymbol[0]

    quotes = live_client.options.quotes(
        option_symbol, output_format=OutputFormat.INTERNAL
    )

    assert isinstance(quotes, OptionsQuotes), quotes
    assert quotes.s == "ok"
    assert quotes.optionSymbol == [option_symbol]
    assert quotes.underlying == [UNDERLYING]
    assert quotes.strike == [live_chain.strike[0]]
    assert quotes.side == [live_chain.side[0]]
    assert isinstance(quotes.expiration[0], datetime.datetime)
    assert isinstance(quotes.updated[0], datetime.datetime)
    assert quotes.bid[0] >= 0 and quotes.ask[0] >= quotes.bid[0]
    assert isinstance(quotes.bid[0], Decimal)
    assert isinstance(quotes.ask[0], Decimal)
    assert isinstance(quotes.openInterest[0], int)


def test_chain_dte_single_value_is_the_closest_expiration(
    live_client: MarketDataClient,
):
    """2.0.0: `dte` is a string now, but a single value still answers with the
    one expiration closest to it (SDK requirements #4: the form the parameter
    already had keeps working, and the server may now read it differently).
    Which of two tied candidates comes back is not asserted."""
    target = 30

    baseline = live_client.options.chain(
        UNDERLYING, strike_limit=1, output_format=OutputFormat.INTERNAL
    )
    available = sorted(set(baseline.dte))
    assert len(available) > 1

    nearest_distance = min(abs(dte - target) for dte in available)
    candidates = {dte for dte in available if abs(dte - target) == nearest_distance}

    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=target,
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(filtered, OptionsChain), filtered
    assert len(filtered.dte) >= 1
    answered = set(filtered.dte)
    assert len(answered) == 1
    assert answered <= candidates


def test_chain_dte_list_matches_the_closest_expiration_for_each_value(
    live_client: MarketDataClient,
):
    """A comma list answers with the closest expiration to each requested
    value, deduplicated. Which of two tied candidates comes back is not
    asserted."""
    requested = (7, 30, 60)

    baseline = live_client.options.chain(
        UNDERLYING, strike_limit=1, output_format=OutputFormat.INTERNAL
    )
    available = sorted(set(baseline.dte))

    def closest(value: int) -> set[int]:
        nearest_distance = min(abs(dte - value) for dte in available)
        return {dte for dte in available if abs(dte - value) == nearest_distance}

    candidates = {value: closest(value) for value in requested}
    every_candidate = set().union(*candidates.values())

    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=",".join(str(value) for value in requested),
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert len(filtered.dte) >= 1
    answered = set(filtered.dte)
    assert answered <= every_candidate
    for value, value_candidates in candidates.items():
        assert value_candidates & answered, (value, value_candidates, answered)
    if (
        len({frozenset(value_candidates) for value_candidates in candidates.values()})
        > 1
    ):
        assert len(answered) > 1


def test_chain_dte_range_returns_every_expiration_within_bounds(
    live_client: MarketDataClient,
):
    """A closed range returns every expiration within it, both ends included.
    AAPL offers more than one expiration within 45 days, so the answer holds
    more than one distinct value and differs from an unfiltered chain."""
    low, high = 0, 45

    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{low}-{high}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert len(filtered.dte) >= 1
    assert all(low <= dte <= high for dte in filtered.dte)
    assert len(set(filtered.dte)) > 1


def test_chain_dte_at_least_returns_every_expiration_at_or_above_the_bound(
    live_client: MarketDataClient,
):
    """`>=30`: whether the API reads the bound as inclusive or exclusive,
    every row answers at or above it. The unfiltered chain has rows below the
    bound, so the filter is shown to have an effect."""
    bound = 30

    baseline = live_client.options.chain(
        UNDERLYING, strike_limit=1, output_format=OutputFormat.INTERNAL
    )
    assert any(dte < bound for dte in baseline.dte)

    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f">={bound}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert len(filtered.dte) >= 1
    assert all(dte >= bound for dte in filtered.dte)


def test_chain_dte_below_returns_every_expiration_at_or_under_the_bound(
    live_client: MarketDataClient,
):
    """`<45`: whichever side of the bound the API includes, every row answers
    at or under it. The unfiltered chain has rows at or above the bound, so
    the filter is shown to have an effect."""
    bound = 45

    baseline = live_client.options.chain(
        UNDERLYING, strike_limit=1, output_format=OutputFormat.INTERNAL
    )
    assert any(dte >= bound for dte in baseline.dte)

    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"<{bound}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert len(filtered.dte) >= 1
    assert all(dte <= bound for dte in filtered.dte)


def test_lookup_resolves_a_human_readable_contract(
    live_client: MarketDataClient, live_chain: OptionsChain
):
    # Round trip: describe the chain's first contract in words and expect the
    # API to hand back the very same OCC symbol.
    expiration = live_chain.expiration[0]
    strike = live_chain.strike[0]
    side = live_chain.side[0]
    lookup = (
        f"{UNDERLYING} {expiration.month}/{expiration.day}/{expiration.year} "
        f"{strike:g} {side}"
    )

    result = live_client.options.lookup(lookup, output_format=OutputFormat.INTERNAL)

    assert isinstance(result, OptionsLookup), result
    assert result.s == "ok"
    assert result.optionSymbol == live_chain.optionSymbol[0]
