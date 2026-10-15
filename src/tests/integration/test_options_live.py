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


@pytest.fixture(scope="module")
def live_chain_wide(live_client: MarketDataClient) -> OptionsChain:
    # A year-wide dte range, used as the baseline the narrower dte expression
    # forms below are checked against. Leaving `days_to_expiration` out
    # entirely is not a usable baseline: the API returns only the nearest
    # expiration when no expiration filter is given at all, which is already
    # narrower than most of the filters below and would make them look like
    # they narrowed the chain even if the server ignored them.
    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration="0-365",
        strike_limit=2,
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(chain, OptionsChain), chain
    return chain


def test_chain_dte_single_value_still_limits_to_one_expiration(
    live_client: MarketDataClient,
):
    # Regression: the form `dte` already had, as an int and as the equivalent
    # string now that the parameter takes either.
    as_int = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=30,
        strike_limit=2,
        output_format=OutputFormat.INTERNAL,
    )
    as_str = live_client.options.chain(
        UNDERLYING,
        days_to_expiration="30",
        strike_limit=2,
        output_format=OutputFormat.INTERNAL,
    )

    for chain in (as_int, as_str):
        assert isinstance(chain, OptionsChain), chain
        assert len(chain.optionSymbol) >= 1
        assert len(set(chain.dte)) == 1

    assert set(as_int.dte) == set(as_str.dte)


def test_chain_dte_comma_list_picks_the_closest_expiration_per_value(
    live_client: MarketDataClient, live_chain_wide: OptionsChain
):
    requested_values = (15, 30, 45)
    available = set(live_chain_wide.dte)

    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration="15,30,45",
        strike_limit=2,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    assert len(chain.optionSymbol) >= 1
    distinct = set(chain.dte)
    assert 1 <= len(distinct) <= 3

    # For each requested value, work out which expiration(s) in the wide
    # baseline are actually closest to it (more than one if two are tied;
    # the API documents "closest" but not how it breaks a tie). Every
    # expiration that came back must be one of those candidates, and every
    # requested value must be represented by at least one of its candidates.
    candidates_by_value = {}
    for value in requested_values:
        closest_distance = min(abs(dte - value) for dte in available)
        candidates_by_value[value] = {
            dte for dte in available if abs(dte - value) == closest_distance
        }

    for value, candidates in candidates_by_value.items():
        assert distinct & candidates, (value, candidates, distinct)
    assert distinct <= set().union(*candidates_by_value.values())


def test_chain_dte_closed_range_is_inclusive_on_both_ends(
    live_client: MarketDataClient, live_chain_wide: OptionsChain
):
    # Anchor the upper bound on an expiration the baseline actually lists
    # near 45 days out, rather than the literal 45: the market lists whatever
    # days it lists, not every integer, and a bound that falls between two
    # real expirations would prove nothing about inclusivity either way.
    boundary = min(set(live_chain_wide.dte), key=lambda dte: abs(dte - 45))
    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"0-{boundary}",
        strike_limit=2,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    assert len(chain.optionSymbol) >= 1
    assert all(0 <= dte <= boundary for dte in chain.dte)
    # The contract exactly at the upper bound is retained, not excluded.
    assert boundary in chain.dte
    assert any(dte > boundary for dte in live_chain_wide.dte)
    assert len(set(chain.dte)) > 1


def test_chain_dte_at_least_operator_is_inclusive_of_the_bound(
    live_client: MarketDataClient, live_chain_wide: OptionsChain
):
    boundary = min(set(live_chain_wide.dte), key=lambda dte: abs(dte - 30))
    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f">={boundary}",
        strike_limit=2,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    assert len(chain.optionSymbol) >= 1
    assert all(dte >= boundary for dte in chain.dte)
    # The contract exactly at the lower bound is retained, not excluded.
    assert boundary in chain.dte
    assert any(dte < boundary for dte in live_chain_wide.dte)


def test_chain_dte_below_operator_is_inclusive_of_the_bound(
    live_client: MarketDataClient, live_chain_wide: OptionsChain
):
    boundary = min(set(live_chain_wide.dte), key=lambda dte: abs(dte - 45))
    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"<{boundary}",
        strike_limit=2,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    assert len(chain.optionSymbol) >= 1
    assert all(dte <= boundary for dte in chain.dte)
    # The contract exactly at the bound is retained, not excluded: `<` reads
    # as inclusive here per the documented contract.
    assert boundary in chain.dte
    assert any(dte > boundary for dte in live_chain_wide.dte)
    assert len(set(chain.dte)) > 1


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
