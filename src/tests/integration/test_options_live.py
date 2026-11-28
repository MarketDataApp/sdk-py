"""Live tests for the options resource: chain, expirations, quotes, lookup."""

import datetime
import operator
from collections.abc import Callable
from decimal import Decimal

import pytest

from marketdata import MarketDataClient, OutputFormat
from marketdata.exceptions import BadRequestError
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


@pytest.fixture(scope="module")
def dte_bound(live_client: MarketDataClient) -> int:
    """Return the `dte` of the AAPL expiration closest to 180 days out.

    Returns:
        A `dte` that an expiration of the chain has, so a comparison against
        it puts that expiration exactly on the bound.
    """
    chain = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=180,
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )
    assert chain.s == "ok"
    return chain.dte[0]


@pytest.mark.parametrize(
    ("prefix", "compare", "keeps_bound"),
    [
        ("<", operator.lt, False),
        ("<=", operator.le, True),
        (">", operator.gt, False),
        (">=", operator.ge, True),
    ],
    ids=["below", "at_most", "above", "at_least"],
)
def test_dte_comparison_at_an_expiration_on_the_bound(
    live_client: MarketDataClient,
    dte_bound: int,
    prefix: str,
    compare: Callable[[int, int], bool],
    keeps_bound: bool,
):
    """Filter the chain by a `dte` comparison whose bound is an expiration.

    `<` and `>` leave that expiration out, `<=` and `>=` keep it, and every
    expiration returned satisfies the comparison. More than one expiration
    comes back, which the nearest-expiration default the API answers with
    when it ignores `dte` cannot do.

    Args:
        prefix: The comparison operator sent before the bound.
        compare: The same comparison, applied to each `dte` returned.
        keeps_bound: Whether the expiration on the bound is returned.
    """
    filtered = live_client.options.chain(
        UNDERLYING,
        days_to_expiration=f"{prefix}{dte_bound}",
        strike_limit=1,
        output_format=OutputFormat.INTERNAL,
    )

    assert filtered.s == "ok"
    returned = set(filtered.dte)
    assert all(compare(dte, dte_bound) for dte in returned), sorted(returned)
    assert (dte_bound in returned) is keeps_bound, (dte_bound, sorted(returned))
    assert len(returned) > 1, sorted(returned)


MODEL_PINNED_DATE = datetime.date(2026, 6, 15)
# `bsm` prices every contract European-style, with no early-exercise value;
# an American method priced against it is the one pair guaranteed to diverge
# on a deep ITM put with months left (the premium of being able to exercise
# early), whichever of the two is the one under test.
MODEL_BASELINE = "bsm"
MODEL_BASELINE_FOR_ITSELF = "bjs"


def _deepest_itm_put_chain(live_client: MarketDataClient, model: str) -> OptionsChain:
    """A historical, `model`-priced chain of deep ITM puts, the pair most
    likely to carry early-exercise value: time for it to matter (`dte=180`)
    and a few strikes deep enough in the money."""
    chain = live_client.options.chain(
        UNDERLYING,
        date=MODEL_PINNED_DATE,
        days_to_expiration=180,
        side="put",
        range="itm",
        strike_limit=10,
        model=model,
        output_format=OutputFormat.INTERNAL,
    )
    assert chain.s == "ok"
    assert chain.optionSymbol, "no ITM put in the chain to price"
    return chain


def _greeks_by_symbol(chain: OptionsChain) -> dict[str, tuple]:
    return dict(
        zip(
            chain.optionSymbol,
            zip(chain.iv, chain.delta, chain.gamma, chain.theta, chain.vega),
        )
    )


@pytest.mark.parametrize("model", ["bsm", "bjs", "crr", "baw"])
def test_chain_model_reaches_the_pricing_engine(
    live_client: MarketDataClient, model: str
):
    """3.0.0: `model` prices a historical chain with a named pricing model.
    Comparing it against a model built on different assumptions (`bsm`,
    European-style, against anything but itself) must show at least one
    contract whose greeks differ: the nearest-expiration default the API
    would answer with if it ignored `model` could not, since both calls ask
    for the same filtered contracts and only `model` differs between them.
    """
    other = MODEL_BASELINE if model != MODEL_BASELINE else MODEL_BASELINE_FOR_ITSELF
    tested = _greeks_by_symbol(_deepest_itm_put_chain(live_client, model))
    baseline = _greeks_by_symbol(_deepest_itm_put_chain(live_client, other))

    common = set(tested) & set(baseline)
    assert common, "no contract in common between the two model calls"
    assert any(tested[symbol] != baseline[symbol] for symbol in common), (
        tested,
        baseline,
    )


def test_chain_model_without_date_is_a_bad_request(live_client: MarketDataClient):
    """3.0.0: the API's documentation says `model` requires the historical
    `date` parameter and rejects its absence with a 400."""
    with pytest.raises(BadRequestError) as exc_info:
        live_client.options.chain(
            UNDERLYING,
            model="bjs",
            strike_limit=1,
            output_format=OutputFormat.INTERNAL,
        )
    assert exc_info.value.status_code == 400


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


def test_quotes_model_without_date_or_range_is_a_bad_request(
    live_client: MarketDataClient, live_chain: OptionsChain
):
    """3.0.0: the API's documentation says `model` requires `date`, `from` or
    `to`, and rejects a quotes request carrying none of them with a 400."""
    option_symbol = live_chain.optionSymbol[0]
    with pytest.raises(BadRequestError) as exc_info:
        live_client.options.quotes(
            option_symbol, model="bjs", output_format=OutputFormat.INTERNAL
        )
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("model", ["bsm", "bjs", "crr", "baw"])
def test_quotes_model_reaches_the_pricing_engine(
    live_client: MarketDataClient, model: str
):
    """3.0.0: see `test_chain_model_reaches_the_pricing_engine`; the same
    deep ITM put, priced under `model` and under a model built on different
    assumptions, must disagree on at least one greek for the same historical
    date."""
    other = MODEL_BASELINE if model != MODEL_BASELINE else MODEL_BASELINE_FOR_ITSELF
    contracts = _deepest_itm_put_chain(live_client, model)
    deepest = contracts.strike.index(max(contracts.strike))
    option_symbol = contracts.optionSymbol[deepest]

    tested = live_client.options.quotes(
        option_symbol,
        date=MODEL_PINNED_DATE,
        model=model,
        output_format=OutputFormat.INTERNAL,
    )
    baseline = live_client.options.quotes(
        option_symbol,
        date=MODEL_PINNED_DATE,
        model=other,
        output_format=OutputFormat.INTERNAL,
    )

    assert tested.s == "ok"
    assert baseline.s == "ok"
    tested_greeks = (
        tested.iv[0],
        tested.delta[0],
        tested.gamma[0],
        tested.theta[0],
        tested.vega[0],
    )
    baseline_greeks = (
        baseline.iv[0],
        baseline.delta[0],
        baseline.gamma[0],
        baseline.theta[0],
        baseline.vega[0],
    )
    assert tested_greeks != baseline_greeks


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
