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


@pytest.fixture(scope="module")
def dte_single_value_picks(live_client: MarketDataClient) -> dict[int, int]:
    """The one expiration (in days) each single `dte` value actually picks.

    Built from the parameter under test itself (never from an unfiltered
    call), at three widely separated values so the later tests have anchors
    that do not depend on the day the suite runs.
    """
    picks: dict[int, int] = {}
    for requested in (1, 30, 365):
        chain = live_client.options.chain(
            UNDERLYING,
            days_to_expiration=requested,
            strike_limit=1,
            output_format=OutputFormat.INTERNAL,
        )
        assert isinstance(chain, OptionsChain), chain
        assert chain.s == "ok"
        unique_dte = set(chain.dte)
        assert len(unique_dte) == 1, chain.dte
        picks[requested] = unique_dte.pop()
    return picks


def test_days_to_expiration_single_value_narrows_to_one_expiration(
    dte_single_value_picks: dict[int, int],
):
    # A higher requested value never picks an earlier expiration than a lower
    # one, and AAPL's chain spans both near-term and far-dated (LEAPS)
    # expirations, so the two ends differ.
    assert (
        dte_single_value_picks[1]
        <= dte_single_value_picks[30]
        <= dte_single_value_picks[365]
    )
    assert dte_single_value_picks[1] != dte_single_value_picks[365]


def test_days_to_expiration_comma_list_matches_the_single_value_union(
    live_client: MarketDataClient, dte_single_value_picks: dict[int, int]
):
    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration="1,30,365",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(chain, OptionsChain), chain
    assert chain.s == "ok"
    assert set(chain.dte) == set(dte_single_value_picks.values())


def test_days_to_expiration_closed_range_keeps_its_inclusive_bounds(
    live_client: MarketDataClient, dte_single_value_picks: dict[int, int]
):
    low, high = dte_single_value_picks[1], dte_single_value_picks[365]

    inclusive = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{low}-{high}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(inclusive, OptionsChain), inclusive
    assert inclusive.s == "ok"
    assert low in inclusive.dte
    assert high in inclusive.dte
    assert all(low <= dte <= high for dte in inclusive.dte)

    narrowed = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{low}-{high - 1}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )
    assert isinstance(narrowed, OptionsChain), narrowed
    assert narrowed.s == "ok"
    assert high not in narrowed.dte


def test_days_to_expiration_at_least_operator_excludes_values_below_it(
    live_client: MarketDataClient, dte_single_value_picks: dict[int, int]
):
    at_least = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=">=30",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(at_least, OptionsChain), at_least
    assert at_least.s == "ok"
    assert all(dte >= 30 for dte in at_least.dte)
    # AAPL always has a contract expiring within days, well under 30.
    assert dte_single_value_picks[1] not in at_least.dte


def test_days_to_expiration_below_operator_excludes_values_at_or_above_it(
    live_client: MarketDataClient, dte_single_value_picks: dict[int, int]
):
    below = live_client.options.chain(
        UNDERLYING,
        days_to_expiration="<45",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert isinstance(below, OptionsChain), below
    assert below.s == "ok"
    assert all(dte < 45 for dte in below.dte)
    # AAPL's farthest-dated (LEAPS) expiration is well beyond 45 days out.
    assert dte_single_value_picks[365] not in below.dte
