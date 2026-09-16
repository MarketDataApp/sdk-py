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
# The output format must not change which values reach the query string and
# which are refused.
EVERY_FORMAT = pytest.mark.parametrize(
    "output_format",
    [
        OutputFormat.INTERNAL,
        OutputFormat.JSON,
        OutputFormat.CSV,
        OutputFormat.DATAFRAME,
    ],
)


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


@pytest.mark.parametrize("filter_type", [StrikeFilter, DeltaFilter])
@pytest.mark.parametrize(
    "build",
    [
        lambda f: f.exact(250),
        lambda f: f.any_of(250, 255),
        lambda f: f.between(250, 260),
        lambda f: f.at_least(250),
        lambda f: f.at_most(250),
        lambda f: f.above(250),
        lambda f: f.below(250),
        lambda f: f.expression("240-260"),
    ],
    ids=["exact", "any_of", "between", "at_least", "at_most", "above", "below", "expr"],
)
def test_every_constructor_keeps_its_own_class(filter_type, build):
    """`==` on a `str` subclass is plain string equality, so a constructor
    that stopped returning its own class would pass unnoticed. Every one of
    them is pinned, the way the repo pins `CsvPath`."""
    assert type(build(filter_type)) is filter_type


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda: StrikeFilter.exact(-250),
            "strike cannot be negative (-250): the API reads a number by its "
            "absolute value, so it would answer for 250 instead of failing",
        ),
        (
            lambda: StrikeFilter.below(-250),
            "strike cannot be negative (-250): the API reads a number by its "
            "absolute value, so it would answer for 250 instead of failing",
        ),
        (
            lambda: StrikeFilter.any_of(250, -255),
            "strike cannot be negative (-255): the API reads a number by its "
            "absolute value, so it would answer for 255 instead of failing",
        ),
        (
            lambda: DeltaFilter.at_least(-0.5),
            "delta cannot be negative (-0.5): the API reads a number by its "
            "absolute value, so it would answer for 0.5 instead of failing",
        ),
        (
            lambda: StrikeFilter.between(-20, 80),
            "low cannot be negative (-20): a range with a minus in it is not "
            "read as a range at all, so the call fails with a 400",
        ),
        (
            lambda: StrikeFilter.between(20, -80),
            "high cannot be negative (-80): a range with a minus in it is not "
            "read as a range at all, so the call fails with a 400",
        ),
        (
            lambda: DeltaFilter.between(-0.5, 0.5),
            "low cannot be negative (-0.5): a range with a minus in it is not "
            "read as a range at all, so the call fails with a 400",
        ),
    ],
)
def test_a_negative_is_refused_with_the_reason_that_applies_to_its_shape(call, message):
    """`parse_input` is `abs(float(value))`, so `strike=-250` answers with the
    strikes at 250 and `>=-0.5` becomes `>=0.5`: the call succeeds and the
    rows are not the ones that were asked for. A range is worse still, since
    a leading minus stops the API reading it as a range at all and the call
    fails with a 400 (#101). The whole sentence is asserted: a `match=` of a
    few words passes on a message that has been rewritten into something
    false, which is how two wrong reasons shipped here before."""
    with pytest.raises(ValueError) as refusal:
        call()

    assert str(refusal.value) == message


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: StrikeFilter.exact(True), "bool"),
        (lambda: StrikeFilter.exact("250"), "must be a number"),
        (lambda: StrikeFilter.exact(float("inf")), "finite"),
        (lambda: StrikeFilter.exact(float("nan")), "finite"),
        (lambda: StrikeFilter.exact(Decimal("nan")), "finite"),
        # A positive exponent travels fine and the API answers 250 for it,
        # measured. What breaks is a minus inside the text (#101, round 2).
        (lambda: StrikeFilter.exact(1e-05), "cannot carry a minus inside it"),
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
@EVERY_FORMAT
def test_the_query_string_carries_what_the_caller_asked_for(
    respx_mock, client, field, passed, sent, output_format
):
    """#101: a number was refused before a request was built, while the public
    docs type `strike` as `float` and the API takes both a number and an
    expression."""
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    client.options.chain("AAPL", **{field: passed}, output_format=output_format)

    params = respx_mock.calls.last.request.url.params
    assert params[field] == sent
    assert params["format"] == ("csv" if output_format == OutputFormat.CSV else "json")


@pytest.mark.parametrize("field", ["strike", "delta"])
@pytest.mark.parametrize("refused", [True, float("inf"), float("nan"), object(), 1e-05])
@EVERY_FORMAT
def test_a_bare_value_the_api_would_misread_never_reaches_a_request(
    respx_mock, client, field, refused, output_format
):
    """Without the field check these do not fail, they mean something else:
    pydantic reads `True` as the int 1, so the call becomes a request for
    strike 1, and an infinity reaches the query as `inf`. The field checks
    them the way a filter does, and no request is built."""
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    with pytest.raises(ValidationError):
        client.options.chain("AAPL", **{field: refused}, output_format=output_format)

    # the client fixture makes its own startup call, so the check is that no
    # chain request was built
    assert not [c for c in respx_mock.calls if "/options/chain/" in str(c.request.url)]


@EVERY_FORMAT
def test_a_negative_strike_never_reaches_a_request(respx_mock, client, output_format):
    """Measured: `strike=-250` answers with the strikes at 250, a 203 with the
    wrong rows in it. The SDK refuses it instead."""
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    with pytest.raises(ValidationError, match="cannot be negative"):
        client.options.chain("AAPL", strike=-250, output_format=output_format)

    # the client fixture makes its own startup call, so the check is that no
    # chain request was built
    assert not [c for c in respx_mock.calls if "/options/chain/" in str(c.request.url)]


def test_a_strike_read_from_a_chain_can_be_passed_back():
    """With money exact (#50) an INTERNAL chain answers its strikes as
    `Decimal`, and that value is a legitimate input to the next call."""
    from_a_previous_chain = Decimal("262.50")

    passed_back = OptionsChainInput(symbol="AAPL", strike=from_a_previous_chain)

    assert passed_back.strike == "262.50"


def test_a_positive_exponent_is_sent_as_it_is():
    """`Decimal("250.00").normalize()` is `Decimal("2.5E+2")`, which is what a
    caller gets from tidying a strike read off an INTERNAL chain. The API
    answers `250` for it, measured, so refusing it would have refused a value
    it understands, with a message telling the caller to pass a Decimal they
    had already passed (#101, round 2)."""
    assert StrikeFilter.exact(Decimal("250.00").normalize()) == "2.5E+2"


def test_a_signed_zero_is_zero():
    """The API answers `0` for `-0.0`, which is what the caller meant, so the
    sign goes rather than the value being refused for a minus nobody wrote."""
    assert StrikeFilter.exact(-0.0) == "0.0"
    assert StrikeFilter.exact(Decimal("-0")) == "0"
