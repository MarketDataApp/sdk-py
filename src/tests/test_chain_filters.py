"""The numeric filters of `options.chain`: `strike` and `delta` (#101).

The API reads both through `parse_numeric_query`. Every shape below was
measured against production on 2026-09-15 with `expiration=2026-09-23`:

    strike=250        -> [250]
    strike=250,255    -> [250, 255]
    strike=250-260    -> [250, 255, 260]
    strike=>=250      -> [250, 255, 260, 265, ...]
    strike=<250       -> [245]
    strike=ATM        -> 400, "Bad parameters"
    strike=-250       -> [250, 250]        the minus is dropped in silence
    delta=0.5         -> deltas [0.5266, -0.4729]
    delta=-0.5        -> the same rows, the API filters on the absolute value
    delta=0.3-0.5     -> deltas [0.4445, 0.3632, -0.3168, -0.3918]
    delta=-0.5-0.5    -> 400, not read as a range at all
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from marketdata import DeltaFilter, StrikeFilter
from marketdata.input_types.base import OutputFormat
from marketdata.input_types.options import OptionsChainInput

CHAIN_URL = "https://api.marketdata.app/v1/options/chain/AAPL/"


@pytest.mark.parametrize(
    ("built", "expression"),
    [
        (StrikeFilter.exact(250), "250"),
        (StrikeFilter.exact(Decimal("262.50")), "262.50"),
        (StrikeFilter.exact(65.1), "65.1"),
        (StrikeFilter.exact(0), "0"),
        (StrikeFilter.any_of(250, 255), "250,255"),
        (StrikeFilter.any_of(Decimal("250.5")), "250.5"),
        (StrikeFilter.between(250, 260), "250-260"),
        (StrikeFilter.between(250, 250), "250-250"),
        (StrikeFilter.at_least(250), ">=250"),
        (StrikeFilter.at_most(250), "<=250"),
        (StrikeFilter.above(250), ">250"),
        (StrikeFilter.below(250), "<250"),
        (StrikeFilter.expression("240-260"), "240-260"),
        (DeltaFilter.exact(0.5), "0.5"),
        (DeltaFilter.exact(-0.5), "-0.5"),
        (DeltaFilter.any_of(-0.3, 0.5), "-0.3,0.5"),
        (DeltaFilter.between(Decimal("0.3"), Decimal("0.5")), "0.3-0.5"),
        (DeltaFilter.at_least(0.5), ">=0.5"),
    ],
)
def test_each_constructor_renders_the_expression_the_api_reads(built, expression):
    assert built == expression
    # `type(built) is type(built).mro()[0]` would be a tautology: the class is
    # pinned by `test_a_filter_keeps_its_own_class` instead.
    assert isinstance(built, str), "it reaches the query string as a string"


@pytest.mark.parametrize("build", [StrikeFilter.exact, DeltaFilter.exact])
def test_a_filter_keeps_its_own_class(build):
    """`==` on a `str` subclass is plain string equality, so a constructor
    that stopped returning its own class would pass unnoticed. The repo pins
    `CsvPath` the same way."""
    assert type(build(250)) is build.__self__


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: StrikeFilter.exact(-250), "cannot be negative"),
        (lambda: StrikeFilter.below(-250), "cannot be negative"),
        (lambda: StrikeFilter.at_least(-250), "cannot be negative"),
        (lambda: StrikeFilter.any_of(250, -255), "cannot be negative"),
        (lambda: StrikeFilter.between(-20, 80), "cannot be negative"),
        (lambda: DeltaFilter.at_least(-0.5), "cannot be negative"),
        (lambda: DeltaFilter.between(-0.5, 0.5), "cannot be negative"),
    ],
)
def test_a_negative_is_refused_where_the_api_would_drop_its_sign(call, message):
    """`parse_input` is `abs(float(value))`, so `strike=-250` answers with the
    strikes at 250 and `>=-0.5` becomes `>=0.5`: the call succeeds and the
    rows are not the ones that were asked for. A range is worse still, since
    a leading minus stops the API reading it as a range at all and the call
    fails with a 400 (#101)."""
    with pytest.raises(ValueError, match=message):
        call()


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: StrikeFilter.exact(True), "bool"),
        (lambda: StrikeFilter.exact("250"), "must be a number"),
        (lambda: StrikeFilter.exact(float("inf")), "finite"),
        (lambda: StrikeFilter.exact(float("nan")), "finite"),
        (lambda: StrikeFilter.exact(Decimal("nan")), "finite"),
        (lambda: StrikeFilter.exact(1e-05), "exponent notation"),
        (lambda: StrikeFilter.exact(Decimal("2.5E+2")), "exponent notation"),
        (lambda: StrikeFilter.any_of(), "at least one"),
        (lambda: StrikeFilter.between(260, 250), "must not be above"),
        (lambda: StrikeFilter.expression(250), "must be a str"),
        (lambda: StrikeFilter.expression("  "), "cannot be empty"),
    ],
)
def test_a_value_that_is_not_one_is_refused_where_it_is_written(call, message):
    """The refusal names the argument, at the call that built it, rather than
    arriving later as a 400 with the SDK's own parameter inside it."""
    with pytest.raises(ValueError, match=message):
        call()


def test_a_delta_keeps_its_sign_where_the_api_reads_the_same_rows_either_way():
    """The API filters on the absolute value of delta and answers both sides,
    measured: `delta=0.5` and `delta=-0.5` return the same rows. A caller
    thinking in put deltas is not corrected."""
    assert DeltaFilter.exact(-0.5) == "-0.5"
    assert DeltaFilter.any_of(-0.3, -0.5) == "-0.3,-0.5"


@pytest.mark.parametrize(
    ("field", "passed", "sent"),
    [
        ("strike", 250, "250"),
        ("strike", 250.0, "250.0"),
        ("strike", 65.1, "65.1"),
        ("strike", Decimal("262.50"), "262.50"),
        ("strike", "250", "250"),
        ("strike", ">=250", ">=250"),
        ("strike", StrikeFilter.between(250, 260), "250-260"),
        ("delta", 0.5, "0.5"),
        ("delta", -0.5, "-0.5"),
        ("delta", "0.3-0.5", "0.3-0.5"),
        ("delta", DeltaFilter.at_least(0.5), ">=0.5"),
    ],
)
def test_the_query_string_carries_what_the_caller_asked_for(
    respx_mock, client, field, passed, sent
):
    """#101: a number was refused before a request was built, while the public
    docs type `strike` as `float` and the API takes both a number and an
    expression."""
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    client.options.chain("AAPL", **{field: passed}, output_format=OutputFormat.JSON)

    assert respx_mock.calls.last.request.url.params[field] == sent


@pytest.mark.parametrize("field", ["strike", "delta"])
@pytest.mark.parametrize("refused", [True, float("inf"), float("nan"), object(), 1e-05])
def test_a_bare_value_the_api_would_misread_never_reaches_a_request(
    respx_mock, client, field, refused
):
    """`urlencode` would stringify any of these on its own: `True` as `True`,
    an infinity as `inf`. The field checks them the way a filter does, and no
    request is made."""
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    with pytest.raises(ValidationError):
        client.options.chain(
            "AAPL", **{field: refused}, output_format=OutputFormat.JSON
        )

    # the client fixture makes its own startup call, so the check is that no
    # chain request was built
    assert not [c for c in respx_mock.calls if "/options/chain/" in str(c.request.url)]


def test_a_negative_strike_never_reaches_a_request(respx_mock, client):
    """Measured: `strike=-250` answers with the strikes at 250, a 203 with the
    wrong rows in it. The SDK refuses it instead."""
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    with pytest.raises(ValidationError, match="cannot be negative"):
        client.options.chain("AAPL", strike=-250, output_format=OutputFormat.JSON)

    # the client fixture makes its own startup call, so the check is that no
    # chain request was built
    assert not [c for c in respx_mock.calls if "/options/chain/" in str(c.request.url)]


def test_a_strike_read_from_a_chain_can_be_passed_back():
    """With money exact (#50) an INTERNAL chain answers its strikes as
    `Decimal`, and that value is a legitimate input to the next call."""
    from_a_previous_chain = Decimal("262.50")

    passed_back = OptionsChainInput(symbol="AAPL", strike=from_a_previous_chain)

    assert passed_back.strike == "262.50"
