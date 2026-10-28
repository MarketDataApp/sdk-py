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
def baseline_dte_values(live_client: MarketDataClient) -> list[int]:
    """The distinct `dte` values the chain offers today, unfiltered.

    A small `strike_limit` keeps the payload down without narrowing which
    expirations come back, since it limits strikes per expiration, not which
    expirations are offered.
    """
    chain = live_client.options.chain(
        UNDERLYING, strike_limit=1, output_format=OutputFormat.INTERNAL
    )
    assert isinstance(chain, OptionsChain), chain
    values = sorted(set(chain.dte))
    assert len(values) >= 4, values
    return values


def _closest(values: list[int], target: int) -> set[int]:
    """The value(s) in ``values`` tied for the smallest distance to ``target``."""
    distances = {value: abs(value - target) for value in values}
    smallest = min(distances.values())
    return {value for value, distance in distances.items() if distance == smallest}


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


def test_dte_single_value_answers_with_the_closest_expiration(
    live_client: MarketDataClient, baseline_dte_values: list[int]
):
    """`dte=N` limits the chain to the expiration(s) closest to `N`. A target
    between two offered values exercises the "closest" match rather than a
    plain equality; which of two equally-close values comes back is not
    asserted, since the API does not document how a tie is broken."""
    low, high = baseline_dte_values[0], baseline_dte_values[1]
    target = (low + high) // 2
    candidates = _closest(baseline_dte_values, target)

    chain = live_client.options.chain(
        UNDERLYING, days_to_expiration=target, output_format=OutputFormat.INTERNAL
    )

    assert isinstance(chain, OptionsChain), chain
    found = set(chain.dte)
    assert found, "no contract came back for a value the chain offers nearby"
    assert found <= candidates, found
    assert found & candidates


def test_dte_list_answers_with_the_closest_expiration_per_value(
    live_client: MarketDataClient, baseline_dte_values: list[int]
):
    """`dte="a,b"` selects the closest expiration for each value, deduplicated.
    The two targets are the lowest and highest values the chain offers, so
    each is already its own closest match and their candidate sets differ,
    which the unfiltered chain (more than two distinct values) would not."""
    first, second = baseline_dte_values[0], baseline_dte_values[-1]
    candidates_first = _closest(baseline_dte_values, first)
    candidates_second = _closest(baseline_dte_values, second)
    assert candidates_first != candidates_second

    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{first},{second}",
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    found = set(chain.dte)
    assert found <= candidates_first | candidates_second, found
    assert found & candidates_first
    assert found & candidates_second
    assert len(found) > 1


def test_dte_range_answers_with_every_expiration_inside_it(
    live_client: MarketDataClient, baseline_dte_values: list[int]
):
    """`dte="low-high"` is a closed range: every expiration within it, both
    ends included. `low` and `high` are the two lowest offered values, and a
    third, higher value the chain offers is left out of the bound on purpose
    so the filtered answer differs from the unfiltered one."""
    low, high, excluded = (
        baseline_dte_values[0],
        baseline_dte_values[1],
        baseline_dte_values[2],
    )

    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{low}-{high}",
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    found = set(chain.dte)
    assert found, found
    assert all(low <= value <= high for value in found), found
    assert len(found) > 1, found
    assert excluded not in found


def test_dte_at_least_excludes_every_value_below_it(
    live_client: MarketDataClient, baseline_dte_values: list[int]
):
    """`dte=">=N"` returns every expiration at or above `N`. The bound is
    asserted as what holds whichever way the API reads it (inclusive or
    exclusive): every returned value is `>= N`. `N` is chosen so the smallest
    offered value falls below it, which the filter has to leave out."""
    threshold = baseline_dte_values[1]
    excluded = baseline_dte_values[0]
    assert excluded < threshold

    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f">={threshold}",
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    found = set(chain.dte)
    assert found, found
    assert all(value >= threshold for value in found), found
    assert excluded not in found


def test_dte_below_excludes_every_value_at_or_above_it(
    live_client: MarketDataClient, baseline_dte_values: list[int]
):
    """`dte="<N"` returns expirations below `N`. The bound is asserted as what
    holds whichever way the API reads it: every returned value is `<= N`. `N`
    is chosen so the largest offered value falls at or above it, which the
    filter has to leave out."""
    threshold = baseline_dte_values[-2]
    excluded = baseline_dte_values[-1]
    assert excluded >= threshold

    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"<{threshold}",
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    found = set(chain.dte)
    assert found, found
    assert all(value <= threshold for value in found), found
    assert excluded not in found
