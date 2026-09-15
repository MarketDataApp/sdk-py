"""The `strike` filter of `options.chain` (#101).

The API reads `strike` as an expression: an exact price, a comma list, an
inclusive range or a one-sided bound. Every shape below was measured against
production on 2026-09-15 with `expiration=2026-09-23&side=call`:

    strike=250       -> [250]
    strike=250,255   -> [250, 255]
    strike=250-260   -> [250, 255, 260]
    strike=>=250     -> [250, 255, 260, 265, ...]
    strike=<250      -> [245]
    strike=ATM       -> 400, "Bad parameters"
"""

from decimal import Decimal

import pytest

from marketdata import StrikeFilter
from marketdata.input_types.base import OutputFormat
from marketdata.input_types.options import OptionsChainInput

CHAIN_URL = "https://api.marketdata.app/v1/options/chain/AAPL/"


@pytest.mark.parametrize(
    ("built", "expression"),
    [
        (StrikeFilter.exact(250), "250"),
        (StrikeFilter.exact(Decimal("262.50")), "262.50"),
        (StrikeFilter.exact(65.1), "65.1"),
        (StrikeFilter.any_of(250, 255), "250,255"),
        (StrikeFilter.any_of(Decimal("250.5")), "250.5"),
        (StrikeFilter.between(250, 260), "250-260"),
        (StrikeFilter.between(250, 250), "250-250"),
        (StrikeFilter.at_least(250), ">=250"),
        (StrikeFilter.at_most(250), "<=250"),
        (StrikeFilter.above(250), ">250"),
        (StrikeFilter.below(250), "<250"),
        (StrikeFilter.expression("240-260"), "240-260"),
    ],
)
def test_each_constructor_renders_the_expression_the_api_reads(built, expression):
    assert built == expression
    assert isinstance(built, str), "it travels to the query string as a string"


def test_a_float_keeps_its_shortest_form_rather_than_its_binary_expansion():
    """`65.1` is not exactly representable, and `Decimal(65.1)` spells out the
    expansion. The API is asked for the strike the caller named."""
    assert StrikeFilter.exact(65.1) == "65.1"
    assert str(Decimal(65.1)).startswith("65.09999")


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
def test_a_price_that_is_not_one_is_refused_where_it_is_written(call, message):
    """The refusal names the argument, at the call that built it, rather than
    arriving as a 400 from the API with the SDK's own parameter in it."""
    with pytest.raises((TypeError, ValueError), match=message):
        call()


@pytest.mark.parametrize(
    ("passed", "sent"),
    [
        (250, "250"),
        (250.0, "250.0"),
        (65.1, "65.1"),
        (Decimal("262.50"), "262.50"),
        ("250", "250"),
        (">=250", ">=250"),
        (StrikeFilter.between(250, 260), "250-260"),
    ],
)
def test_the_query_string_carries_what_the_caller_asked_for(
    respx_mock, client, passed, sent
):
    """#101: a number was refused before a request was built, while the public
    docs type this parameter `float` and the API takes both a number and an
    expression."""
    respx_mock.get(url__startswith=CHAIN_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    client.options.chain("AAPL", strike=passed, output_format=OutputFormat.JSON)

    assert respx_mock.calls.last.request.url.params["strike"] == sent


def test_a_strike_read_from_a_chain_can_be_passed_back():
    """With money exact (#50) an INTERNAL chain answers its strikes as
    `Decimal`, and that value is a legitimate input to the next call."""
    from_a_previous_chain = Decimal("262.50")

    assert (
        OptionsChainInput(symbol="AAPL", strike=from_a_previous_chain).strike
        == "262.50"
    )
