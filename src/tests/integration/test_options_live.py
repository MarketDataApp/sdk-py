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


def test_dte_single_value_narrows_to_the_nearest_expiration(
    live_client: MarketDataClient,
):
    """A single `dte` value answers with the one expiration closest to it, not
    always the same one: two values far apart pick two different
    expirations."""
    near = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=1,
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )
    far = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=365,
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert near.s == "ok"
    assert far.s == "ok"
    assert len(near.dte) >= 1
    assert len(far.dte) >= 1
    assert len(set(near.dte)) == 1
    assert len(set(far.dte)) == 1
    # If the server ignored `dte`, both calls would answer with the same
    # default (nearest) expiration; two targets picking two different
    # expirations is what proves the value is read.
    assert near.dte[0] != far.dte[0]


def test_dte_comma_list_keeps_only_the_requested_expirations(
    live_client: MarketDataClient,
):
    """A comma-separated `dte` list answers with the expiration closest to
    each value, deduplicated, not the whole chain."""
    near = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=1,
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )
    far = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=365,
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )
    near_dte, far_dte = near.dte[0], far.dte[0]

    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{near_dte},{far_dte},{far_dte}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert filtered.s == "ok"
    assert len(filtered.dte) >= 1
    # Repeating `far_dte` is deduplicated to the same two expirations; if the
    # server ignored the list it would answer with the nearest expiration
    # alone, missing `far_dte` entirely.
    assert set(filtered.dte) == {near_dte, far_dte}


def test_dte_closed_range_is_inclusive_at_both_ends(live_client: MarketDataClient):
    """A closed `dte` range such as `N-N` includes the boundary itself: an
    expiration that is not the nearest one is kept, not excluded."""
    far = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=180,
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )
    anchor = far.dte[0]

    ranged = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{anchor}-{anchor}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert ranged.s == "ok"
    assert len(ranged.dte) >= 1
    # If the server ignored the range it would answer with the default
    # (nearest) expiration instead, which is not this far-out one; if it
    # read the range as exclusive, a single-point range would match nothing.
    assert set(ranged.dte) == {anchor}


def test_dte_at_least_keeps_only_expirations_at_or_beyond_the_bound(
    live_client: MarketDataClient,
):
    """`>=N` returns every expiration whose `dte` is N or more, inclusive."""
    bound = 30
    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f">={bound}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )
    # With no expiration filter at all the API answers the nearest expiration
    # only, so `expiration="all"` is what the SDK already documents as the
    # way to see every expiration at once.
    unfiltered = live_client.options.chain(
        UNDERLYING,
        expiration="all",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert filtered.s == "ok"
    assert len(filtered.dte) >= 1
    assert all(dte >= bound for dte in filtered.dte)
    # AAPL always carries an expiration under 30 days out (its weeklies), so
    # the unfiltered answer could never pass the same bound.
    assert any(dte < bound for dte in unfiltered.dte)


def test_dte_below_keeps_only_expirations_short_of_the_bound(
    live_client: MarketDataClient,
):
    """`<N` returns every expiration whose `dte` is strictly under N."""
    bound = 45
    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"<{bound}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert filtered.s == "ok"
    assert len(filtered.dte) >= 1
    assert all(dte < bound for dte in filtered.dte)
    # If the server ignored the bound it would answer with the default
    # (nearest) expiration alone; AAPL always carries several expirations
    # under 45 days out (its weeklies and a monthly), so more than one
    # distinct value here is what proves the bound, not the default, is at
    # work.
    assert len(set(filtered.dte)) > 1


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
