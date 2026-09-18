"""Tests for the `strike` and `delta` filters of `options.chain`."""

import subprocess
import sys
from decimal import Decimal
from fractions import Fraction

import pytest
from pydantic import ValidationError

from marketdata import DeltaFilter, StrikeFilter
from marketdata.input_types import filters
from marketdata.input_types.base import OutputFormat
from marketdata.input_types.options import OptionsChainInput

CHAIN_URL = "https://api.marketdata.app/v1/options/chain/AAPL/"
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
        (DeltaFilter.nearest(0.5), "0.5"),
        (DeltaFilter.nearest(-0.5), "-0.5"),
        (DeltaFilter.any_of(-0.3, 0.5), "-0.3,0.5"),
        (DeltaFilter.between(Decimal("0.3"), Decimal("0.5")), "0.3-0.5"),
        (DeltaFilter.at_least(0.5), ">=0.5"),
    ],
)
def test_each_constructor_renders_the_expression_the_api_reads(built, expression):
    assert built == expression
    assert isinstance(built, str), "it reaches the query string as a string"


@pytest.mark.parametrize("filter_type", [StrikeFilter, DeltaFilter])
@pytest.mark.parametrize(
    "build",
    [
        lambda f: (f.exact if f is StrikeFilter else f.nearest)(0.5),
        lambda f: f.any_of(0.25, 0.5),
        lambda f: f.between(0.25, 0.5),
        lambda f: f.at_least(0.5),
        lambda f: f.at_most(0.5),
        lambda f: f.above(0.5),
        lambda f: f.below(0.5),
        lambda f: f.expression("240-260"),
    ],
    ids=[
        "single",
        "any_of",
        "between",
        "at_least",
        "at_most",
        "above",
        "below",
        "expr",
    ],
)
def test_every_constructor_keeps_its_own_class(filter_type, build):
    """`==` on a `str` subclass cannot tell the classes apart, so each is pinned."""
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
    """The whole message is asserted, so a rewritten reason fails."""
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
        (lambda: StrikeFilter.any_of(), "at least one"),
        (lambda: StrikeFilter.between(260, 250), "must not be above"),
        (lambda: StrikeFilter.expression(250), "must be a str"),
        (lambda: StrikeFilter.expression("  "), "cannot be empty"),
    ],
)
def test_a_value_that_is_not_one_is_refused_where_it_is_written(call, message):
    with pytest.raises(ValueError, match=message):
        call()


TOO_FAR = "is too far from zero for a float ({}): the API would read it as an infinity"
TOO_CLOSE = "is too close to zero for a float ({}): the API would read it as 0"


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            lambda: StrikeFilter.exact(Decimal("1E+400")),
            "strike " + TOO_FAR.format("1.000e+400"),
        ),
        (
            lambda: StrikeFilter.exact(Decimal("1.8E+308")),
            "strike " + TOO_FAR.format("1.800e+308"),
        ),
        (
            lambda: StrikeFilter.at_least(Decimal("-1E+999999999999999999")),
            "strike " + TOO_FAR.format("-1.000e+999999999999999999"),
        ),
        (
            lambda: StrikeFilter.exact(2**1024 - 1),
            "strike " + TOO_FAR.format("an integer of 1024 bits"),
        ),
        (
            lambda: StrikeFilter.exact(10**400),
            "strike " + TOO_FAR.format("an integer of 1329 bits"),
        ),
        (
            lambda: StrikeFilter.exact(Fraction(10**400)),
            "strike " + TOO_FAR.format("a Fraction"),
        ),
        (
            lambda: DeltaFilter.nearest(Decimal("1E-400")),
            "delta " + TOO_CLOSE.format("1.000e-400"),
        ),
        (
            lambda: DeltaFilter.nearest(Decimal("-1E-999999999999999999")),
            "delta " + TOO_CLOSE.format("-1.000e-999999999999999999"),
        ),
        (
            lambda: DeltaFilter.nearest(Fraction(1, 10**400)),
            "delta " + TOO_CLOSE.format("a Fraction"),
        ),
        (
            lambda: StrikeFilter.exact(Fraction(-1, 10**400)),
            "strike " + TOO_CLOSE.format("a Fraction"),
        ),
    ],
)
def test_a_number_a_float_cannot_hold_is_refused_with_what_the_api_would_read(
    call, message
):
    with pytest.raises(ValueError) as refusal:
        call()

    assert str(refusal.value) == message


def test_a_huge_integer_is_refused_before_its_digits_are_read(monkeypatch):
    """Building a `Decimal` from the integer, quadratic in its digits, fails here."""

    class NoHugeDecimal(Decimal):
        def __new__(cls, value="0", context=None):
            too_big = isinstance(value, int) and value.bit_length() > 1024
            assert not too_big, "a Decimal was built from the integer's digits"
            return super().__new__(cls, value, context)

    monkeypatch.setattr(filters, "Decimal", NoHugeDecimal)
    huge = 10**100_000

    with pytest.raises(ValueError) as refusal:
        StrikeFilter.exact(huge)

    assert str(refusal.value) == "strike " + TOO_FAR.format(
        f"an integer of {huge.bit_length()} bits"
    )


def test_importing_the_filters_leaves_a_decimal_context_alone():
    """Importing the module neither trips nor flags a `FloatOperation` trap."""
    code = (
        "import decimal\n"
        "decimal.getcontext().traps[decimal.FloatOperation] = True\n"
        "import marketdata.input_types.filters\n"
        "print(decimal.getcontext().flags[decimal.FloatOperation])\n"
    )

    run = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )

    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "False"


def test_a_delta_keeps_its_sign_where_the_api_reads_the_same_rows_either_way():
    assert DeltaFilter.nearest(-0.5) == "-0.5"
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
        ("delta", 1, "1"),
        ("delta", -1, "-1"),
        ("strike", 30, "30"),
        ("delta", "0.3-0.5", "0.3-0.5"),
        ("delta", DeltaFilter.at_least(0.5), ">=0.5"),
        # plain digits, never an exponent
        ("strike", 1e-05, "0.00001"),
        ("strike", Decimal("2.5E+2"), "250"),
        ("delta", -0.00001, "-0.00001"),
        ("delta", DeltaFilter.at_most(0.00005), "<=0.00005"),
    ],
)
@EVERY_FORMAT
def test_the_query_string_carries_what_the_caller_asked_for(
    respx_mock, client, field, passed, sent, output_format
):
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    client.options.chain("AAPL", **{field: passed}, output_format=output_format)

    params = respx_mock.calls.last.request.url.params
    assert params[field] == sent
    assert params["format"] == ("csv" if output_format == OutputFormat.CSV else "json")


@pytest.mark.parametrize("field", ["strike", "delta"])
@pytest.mark.parametrize(
    "refused", [True, float("inf"), float("nan"), object(), Decimal("1E+400")]
)
@EVERY_FORMAT
def test_a_bare_value_the_api_would_misread_never_reaches_a_request(
    respx_mock, client, field, refused, output_format
):
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    with pytest.raises(ValidationError):
        client.options.chain("AAPL", **{field: refused}, output_format=output_format)

    # the client fixture makes its own startup call
    assert not [c for c in respx_mock.calls if "/options/chain/" in str(c.request.url)]


@EVERY_FORMAT
def test_a_negative_strike_never_reaches_a_request(respx_mock, client, output_format):
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    with pytest.raises(ValidationError, match="cannot be negative"):
        client.options.chain("AAPL", strike=-250, output_format=output_format)

    # the client fixture makes its own startup call
    assert not [c for c in respx_mock.calls if "/options/chain/" in str(c.request.url)]


def test_each_filter_names_its_single_value_for_what_the_api_does():
    """A strike is matched exactly and a delta by the nearest contract."""
    assert not hasattr(DeltaFilter, "exact")
    assert not hasattr(StrikeFilter, "nearest")


def test_a_number_is_held_as_the_text_that_is_sent():
    """The fields hold the text sent and are annotated `str | None`."""
    chain_input = OptionsChainInput(symbol="AAPL", strike=250, delta=0.5)

    assert (chain_input.strike, chain_input.delta) == ("250", "0.5")
    for name in ("strike", "delta"):
        assert OptionsChainInput.model_fields[name].annotation == (str | None)


def test_a_strike_read_from_a_chain_can_be_passed_back():
    """An INTERNAL chain answers strikes as `Decimal`, which the next call takes."""
    from_a_previous_chain = Decimal("262.50")

    passed_back = OptionsChainInput(symbol="AAPL", strike=from_a_previous_chain)

    assert passed_back.strike == "262.50"


@pytest.mark.parametrize(
    ("build", "expression"),
    [
        (lambda: StrikeFilter.exact(Decimal("250.00").normalize()), "250"),
        (lambda: StrikeFilter.exact(1e16), "10000000000000000"),
        (lambda: StrikeFilter.exact(1e-05), "0.00001"),
        (lambda: StrikeFilter.exact(Decimal("1E-5")), "0.00001"),
        (lambda: DeltaFilter.nearest(Decimal("1E-7")), "0.0000001"),
        (lambda: StrikeFilter.exact(5e-324), "0." + "0" * 323 + "5"),
        (lambda: StrikeFilter.exact(Decimal("0E-7")), "0.0000000"),
        # a zero past a float's last decimal place is sent as 0
        (lambda: StrikeFilter.exact(Decimal("0E-400")), "0"),
        (lambda: StrikeFilter.exact(Decimal("-0E-999999999999999999")), "0"),
        (lambda: StrikeFilter.exact(Decimal("0E+999999999999999999")), "0"),
        (lambda: StrikeFilter.exact(Fraction(1, 4)), "0.25"),
        (lambda: StrikeFilter.any_of(1e-05, 250), "0.00001,250"),
        (lambda: StrikeFilter.between(0.00001, 0.5), "0.00001-0.5"),
        (lambda: DeltaFilter.nearest(-0.00001), "-0.00001"),
        (lambda: DeltaFilter.at_most(0.00005), "<=0.00005"),
    ],
)
def test_a_number_travels_as_plain_digits(build, expression):
    assert build() == expression


def test_a_signed_zero_is_zero():
    assert StrikeFilter.exact(-0.0) == "0.0"
    assert StrikeFilter.exact(Decimal("-0")) == "0"


OUT_OF_RANGE = "is out of range ({}): a delta is between -1 and 1"
TOO_LARGE = pytest.mark.parametrize(
    ("outside", "shown"),
    [
        (1.0001, "1.0001"),
        (30, "30"),
        (Decimal("30"), "30"),
        # checked on the digits written, though a float reads them as 1.0
        (Decimal("1.0000000000000001"), "1.0000000000000001"),
    ],
)


@TOO_LARGE
@pytest.mark.parametrize(
    ("build", "argument"),
    [
        (DeltaFilter.nearest, "delta"),
        (DeltaFilter.any_of, "delta"),
        (lambda value: DeltaFilter.any_of(0.5, value), "delta"),
        (lambda value: DeltaFilter.between(value, 0.5), "low"),
        (lambda value: DeltaFilter.between(0.5, value), "high"),
        (DeltaFilter.at_least, "delta"),
        (DeltaFilter.at_most, "delta"),
        (DeltaFilter.above, "delta"),
        (DeltaFilter.below, "delta"),
    ],
    ids=[
        "nearest",
        "any_of",
        "any_of_second",
        "between_low",
        "between_high",
        "at_least",
        "at_most",
        "above",
        "below",
    ],
)
def test_a_delta_above_one_is_refused_by_every_constructor(
    build, argument, outside, shown
):
    with pytest.raises(ValueError) as refusal:
        build(outside)

    assert str(refusal.value) == f"{argument} " + OUT_OF_RANGE.format(shown)


@pytest.mark.parametrize(("outside", "shown"), [(-1.0001, "-1.0001"), (-30, "-30")])
@pytest.mark.parametrize(
    "build",
    [
        DeltaFilter.nearest,
        DeltaFilter.any_of,
        lambda value: DeltaFilter.any_of(-0.5, value),
    ],
    ids=["nearest", "any_of", "any_of_second"],
)
def test_a_negative_delta_below_minus_one_is_refused(build, outside, shown):
    with pytest.raises(ValueError) as refusal:
        build(outside)

    assert str(refusal.value) == "delta " + OUT_OF_RANGE.format(shown)


@pytest.mark.parametrize(
    ("build", "expression"),
    [
        (lambda: DeltaFilter.nearest(1), "1"),
        (lambda: DeltaFilter.nearest(-1), "-1"),
        (lambda: DeltaFilter.nearest(Decimal("-1.000")), "-1.000"),
        (lambda: DeltaFilter.any_of(-1, 1), "-1,1"),
        (lambda: DeltaFilter.between(0.5, 1), "0.5-1"),
        (lambda: DeltaFilter.between(1, 1), "1-1"),
        (lambda: DeltaFilter.between(0.3, 0.5), "0.3-0.5"),
        (lambda: DeltaFilter.at_least(1), ">=1"),
        (lambda: DeltaFilter.at_most(1.0), "<=1.0"),
        (lambda: DeltaFilter.above(1), ">1"),
        (lambda: DeltaFilter.below(1), "<1"),
    ],
)
def test_a_delta_from_minus_one_to_one_is_sent(build, expression):
    assert build() == expression


def test_a_delta_range_is_ordered_as_written():
    with pytest.raises(ValueError) as refusal:
        DeltaFilter.between(0.5, 0.3)

    assert str(refusal.value) == "low must not be above high: 0.5-0.3"


@pytest.mark.parametrize(
    ("build", "expression"),
    [
        (lambda: StrikeFilter.exact(30), "30"),
        (lambda: StrikeFilter.any_of(0.5, 30), "0.5,30"),
        (lambda: StrikeFilter.between(0.5, 30), "0.5-30"),
        (lambda: StrikeFilter.at_least(30), ">=30"),
        (lambda: StrikeFilter.at_most(30), "<=30"),
        (lambda: StrikeFilter.above(30), ">30"),
        (lambda: StrikeFilter.below(30), "<30"),
    ],
)
def test_a_strike_above_one_is_sent(build, expression):
    assert build() == expression


def test_a_delta_expression_is_not_checked_against_the_range():
    assert DeltaFilter.expression("0.5-30") == "0.5-30"


@pytest.mark.parametrize(
    ("outside", "shown"),
    [(30, "30"), (-30, "-30"), (1.0001, "1.0001"), (Decimal("30"), "30")],
)
@EVERY_FORMAT
def test_a_bare_delta_outside_minus_one_to_one_never_reaches_a_request(
    respx_mock, client, outside, shown, output_format
):
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    with pytest.raises(ValidationError) as refusal:
        client.options.chain("AAPL", delta=outside, output_format=output_format)

    assert "delta " + OUT_OF_RANGE.format(shown) in str(refusal.value)
    # the client fixture makes its own startup call
    assert not [c for c in respx_mock.calls if "/options/chain/" in str(c.request.url)]
