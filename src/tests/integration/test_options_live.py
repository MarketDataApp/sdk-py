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


@pytest.fixture
def live_chain_dte_nearest(live_client: MarketDataClient) -> OptionsChain:
    # Far enough out (about three months) that AAPL always has both a nearer
    # and a farther expiration to tell the boundary tests below apart.
    # Function-scoped (unlike `live_chain` above) so each test derives its
    # boundary from its own fresh call: a module-scoped boundary reused by
    # several later calls would drift by one if the run crossed midnight
    # US/Eastern between them.
    chain = live_client.options.chain(
        UNDERLYING, days_to_expiration=90, output_format=OutputFormat.INTERNAL
    )
    assert isinstance(chain, OptionsChain), chain
    assert chain.s == "ok"
    return chain


def test_dte_single_value_narrows_to_the_nearest_expiration(
    live_chain_dte_nearest: OptionsChain,
):
    """2.0.0: a single `dte` still limits the chain to the one expiration
    closest to the value given, the way the plain integer did before the
    API widened the parameter to a string."""
    assert len(set(live_chain_dte_nearest.expiration)) == 1
    assert len(set(live_chain_dte_nearest.dte)) == 1


def test_dte_comma_list_unions_the_nearest_expiration_per_value(
    live_client: MarketDataClient,
):
    """A comma-separated `dte` selects the closest expiration for each value,
    deduplicated: the union of three single-value calls."""
    targets = (15, 30, 45)
    expected_expirations: set[datetime.datetime] = set()
    for target in targets:
        single = live_client.options.chain(
            UNDERLYING, days_to_expiration=target, output_format=OutputFormat.INTERNAL
        )
        assert single.s == "ok"
        expected_expirations |= set(single.expiration)

    combined = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=",".join(str(target) for target in targets),
        output_format=OutputFormat.INTERNAL,
    )

    assert combined.s == "ok"
    assert set(combined.expiration) == expected_expirations


def test_dte_closed_range_collapsed_to_a_point_includes_that_point(
    live_client: MarketDataClient, live_chain_dte_nearest: OptionsChain
):
    """A closed range is inclusive: collapsed to a single boundary (`N-N`) it
    must return exactly the expiration a bare `dte=N` returns."""
    boundary = live_chain_dte_nearest.dte[0]

    collapsed = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{boundary}-{boundary}",
        output_format=OutputFormat.INTERNAL,
    )

    assert collapsed.s == "ok"
    assert set(collapsed.expiration) == set(live_chain_dte_nearest.expiration)


def test_dte_closed_range_spans_every_expiration_within_its_bounds(
    live_client: MarketDataClient,
):
    """A closed range is not only the nearest expiration to either end: it
    returns every expiration whose `dte` falls between the two, inclusive."""
    low_chain = live_client.options.chain(
        UNDERLYING, days_to_expiration=15, output_format=OutputFormat.INTERNAL
    )
    high_chain = live_client.options.chain(
        UNDERLYING, days_to_expiration=45, output_format=OutputFormat.INTERNAL
    )
    assert low_chain.s == "ok"
    assert high_chain.s == "ok"
    low, high = low_chain.dte[0], high_chain.dte[0]
    assert low < high, "the two baseline calls landed on the same expiration"

    ranged = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{low}-{high}",
        output_format=OutputFormat.INTERNAL,
    )

    assert ranged.s == "ok"
    assert all(low <= dte <= high for dte in ranged.dte)
    assert low in set(ranged.dte)
    assert high in set(ranged.dte)
    # A chunk ignoring the range would still answer with the nearest
    # expiration alone; the range has to bring back more than that one.
    assert len(set(ranged.expiration)) > 1


def test_dte_at_least_includes_the_boundary(
    live_client: MarketDataClient, live_chain_dte_nearest: OptionsChain
):
    """`>=N` is inclusive of `N` itself, the way `strike` and `delta` read it."""
    boundary = live_chain_dte_nearest.dte[0]

    at_or_after = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f">={boundary}",
        output_format=OutputFormat.INTERNAL,
    )

    assert at_or_after.s == "ok"
    assert all(dte >= boundary for dte in at_or_after.dte)
    assert boundary in set(at_or_after.dte)


def test_dte_below_excludes_the_boundary(
    live_client: MarketDataClient, live_chain_dte_nearest: OptionsChain
):
    """`<N` leaves `N` itself out, the way `strike` and `delta` read it."""
    boundary = live_chain_dte_nearest.dte[0]

    before = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"<{boundary}",
        output_format=OutputFormat.INTERNAL,
    )

    assert before.s == "ok"
    assert all(dte < boundary for dte in before.dte)
    assert boundary not in set(before.dte)


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
