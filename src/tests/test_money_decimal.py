"""Money is a ``Decimal`` in the INTERNAL models, and only there (#50).

The INTERNAL path of a resource with money fields decodes the body with
``parse_float=Decimal``, and every model then puts each number back where its
annotation says: Decimals in the money fields, the plain parse's floats
everywhere else. The DataFrame and JSON outputs keep the plain float parse.
"""

import array
import copy
import csv
import dataclasses
import datetime
import importlib
import inspect
import json
import math
import pathlib
import pickle
import pkgutil
import typing
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from unittest.mock import patch

import httpx
import numpy as np
import pandas as pd
import polars as pl
import pytest
import pytz

import marketdata.output_types
from marketdata.exceptions import ParseError
from marketdata.input_types.base import OutputFormat
from marketdata.output_types.funds_candles import (
    FundsCandle,
    FundsCandlesHumanReadable,
)
from marketdata.output_types.money import (
    coerce_numbers,
    decimal_fields,
    decimal_to_float,
    to_decimal,
)
from marketdata.output_types.options_chain import (
    OptionsChain,
    OptionsChainHumanReadable,
)
from marketdata.output_types.options_quotes import (
    OptionsQuotes,
    OptionsQuotesHumanReadable,
)
from marketdata.output_types.stocks_candles import (
    StockCandle,
    StockCandlesHumanReadable,
)
from marketdata.output_types.stocks_earnings import (
    StockEarnings,
    StockEarningsHumanReadable,
)
from marketdata.output_types.stocks_prices import (
    StockPrice,
    StockPricesHumanReadable,
)
from marketdata.output_types.stocks_quotes import (
    StockQuote,
    StockQuotesHumanReadable,
)
from marketdata.resources.base import merged_model_errors

DATA_DIR = pathlib.Path(__file__).parent / "data"
API = "https://api.marketdata.app"
OPTION = "AAPL271217C00255000"

# More digits than a double holds, so a float parse reads it as 65.1 and only
# a parse that never goes through a float can hand it to the model intact. The
# trailing zero is the API's own scale, which a normalizing parse would drop.
EXACT = "65.100000000000000000010"

OPTIONS_MONEY = {
    "strike",
    "bid",
    "mid",
    "ask",
    "last",
    "intrinsicValue",
    "extrinsicValue",
    "underlyingPrice",
}
OPTIONS_MONEY_HUMAN = {
    "Strike",
    "Bid",
    "Mid",
    "Ask",
    "Last",
    "Intrinsic_Value",
    "Extrinsic_Value",
    "Underlying_Price",
}

# The scope table of #50, model by model. Every other model holds no money.
MONEY_FIELDS = {
    StockQuote: {
        "ask",
        "bid",
        "mid",
        "last",
        "change",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
    },
    StockQuotesHumanReadable: {
        "Ask",
        "Bid",
        "Mid",
        "Last",
        "Change_Price",
        "Fifty_Two_Week_High",
        "Fifty_Two_Week_Low",
    },
    StockPrice: {"mid", "change"},
    StockPricesHumanReadable: {"Mid", "Change_Price"},
    StockCandle: {"o", "h", "l", "c"},
    StockCandlesHumanReadable: {"Open", "High", "Low", "Close"},
    FundsCandle: {"o", "h", "l", "c"},
    FundsCandlesHumanReadable: {"Open", "High", "Low", "Close"},
    StockEarnings: {"reportedEPS", "estimatedEPS", "surpriseEPS"},
    StockEarningsHumanReadable: {"Reported_EPS", "Estimated_EPS", "Surprise_EPS"},
    OptionsChain: OPTIONS_MONEY,
    OptionsChainHumanReadable: OPTIONS_MONEY_HUMAN,
    OptionsQuotes: OPTIONS_MONEY,
    OptionsQuotesHumanReadable: OPTIONS_MONEY_HUMAN,
}


@dataclasses.dataclass(frozen=True)
class Case:
    fixture: str
    url: str
    call: object
    # A money column of the fixture with a fractional value in its first row,
    # and how to read that value back from an INTERNAL result.
    column: str | None = None
    read: object = None


MONEY_CASES = {
    "stocks.quotes": Case(
        "stocks_quotes_response_200",
        f"{API}/v1/stocks/quotes/",
        lambda c, **kw: c.stocks.quotes(["AAPL", "MSFT"], **kw),
        "bid",
        lambda r: r[0].bid,
    ),
    "stocks.quotes human": Case(
        "stocks_quotes_human_response_200",
        f"{API}/v1/stocks/quotes/",
        lambda c, **kw: c.stocks.quotes(
            ["AAPL", "MSFT"], use_human_readable=True, **kw
        ),
        "Bid",
        lambda r: r[0].Bid,
    ),
    "stocks.prices": Case(
        "stocks_prices_response_200",
        f"{API}/v1/stocks/prices/",
        lambda c, **kw: c.stocks.prices(["AAPL", "TSLA"], **kw),
        "mid",
        lambda r: r[0].mid,
    ),
    "stocks.prices human": Case(
        "stocks_prices_human_response_200",
        f"{API}/v1/stocks/prices/",
        lambda c, **kw: c.stocks.prices(
            ["AAPL", "TSLA"], use_human_readable=True, **kw
        ),
        "Mid",
        lambda r: r[0].Mid,
    ),
    "stocks.candles": Case(
        "stocks_candles_response_200",
        f"{API}/v1/stocks/candles/D/AAPL/",
        lambda c, **kw: c.stocks.candles("AAPL", resolution="D", **kw),
        "c",
        lambda r: r[0].c,
    ),
    "stocks.candles human": Case(
        "stocks_candles_human_response_200",
        f"{API}/v1/stocks/candles/D/AAPL/",
        lambda c, **kw: c.stocks.candles(
            "AAPL", resolution="D", use_human_readable=True, **kw
        ),
        "Close",
        lambda r: r[0].Close,
    ),
    "funds.candles": Case(
        "funds_candles_response_200",
        f"{API}/v1/funds/candles/D/VFINX/",
        lambda c, **kw: c.funds.candles("VFINX", resolution="D", **kw),
        "c",
        lambda r: r[0].c,
    ),
    "funds.candles human": Case(
        "funds_candles_human_response_200",
        f"{API}/v1/funds/candles/D/VFINX/",
        lambda c, **kw: c.funds.candles(
            "VFINX", resolution="D", use_human_readable=True, **kw
        ),
        "Close",
        lambda r: r[0].Close,
    ),
    "stocks.earnings": Case(
        "stocks_earnings_response_200",
        f"{API}/v1/stocks/earnings/AAPL/",
        lambda c, **kw: c.stocks.earnings("AAPL", **kw),
        "estimatedEPS",
        lambda r: r.estimatedEPS[0],
    ),
    "stocks.earnings human": Case(
        "stocks_earnings_human_response_200",
        f"{API}/v1/stocks/earnings/AAPL/",
        lambda c, **kw: c.stocks.earnings("AAPL", use_human_readable=True, **kw),
        "Estimated EPS",
        lambda r: r.Estimated_EPS[0],
    ),
    "options.chain": Case(
        "options_chain_response_200",
        f"{API}/v1/options/chain/AAPL/",
        lambda c, **kw: c.options.chain("AAPL", **kw),
        "bid",
        lambda r: r.bid[0],
    ),
    "options.chain human": Case(
        "options_chain_human_response_200",
        f"{API}/v1/options/chain/AAPL/",
        lambda c, **kw: c.options.chain("AAPL", use_human_readable=True, **kw),
        "Bid",
        lambda r: r.Bid[0],
    ),
    "options.quotes": Case(
        "options_quotes_response_200",
        f"{API}/v1/options/quotes/{OPTION}/",
        lambda c, **kw: c.options.quotes(OPTION, **kw),
        "bid",
        lambda r: r.bid[0],
    ),
    "options.quotes human": Case(
        "options_quotes_human_response_200",
        f"{API}/v1/options/quotes/{OPTION}/",
        lambda c, **kw: c.options.quotes(OPTION, use_human_readable=True, **kw),
        "Bid",
        lambda r: r.Bid[0],
    ),
}

# The keys of each fixture that hold a date. Under `dateformat=spreadsheet`
# the API writes them as numbers with a fraction, which the exact parse turns
# into Decimals.
DATE_KEYS = {
    "stocks.quotes": ("updated",),
    "stocks.quotes human": ("Date",),
    "stocks.prices": ("updated",),
    "stocks.prices human": ("Date",),
    "stocks.candles": ("t",),
    "stocks.candles human": ("Date",),
    "funds.candles": ("t",),
    "funds.candles human": ("Date",),
    "stocks.earnings": ("date", "reportDate", "updated"),
    "stocks.earnings human": ("Date", "Report Date", "Updated"),
    "options.chain": ("expiration", "firstTraded", "updated"),
    "options.chain human": ("Expiration Date", "First Traded", "Date"),
    "options.quotes": ("expiration", "firstTraded", "updated"),
    "options.quotes human": ("Expiration Date", "First Traded", "Date"),
}
# 46003.5 days after 1899-12-30.
SPREADSHEET_DATE = "46003.5"
SPREADSHEET_DATETIME = pytz.timezone("US/Eastern").localize(
    datetime.datetime(2025, 12, 12, 12, 0)
)

# The resources with no money keep the plain parse on every path.
OTHER_CASES = {
    "markets.status": Case(
        "markets_status_response_200",
        f"{API}/v1/markets/status/",
        lambda c, **kw: c.markets.status(**kw),
    ),
    "markets.status human": Case(
        "markets_status_human_response_200",
        f"{API}/v1/markets/status/",
        lambda c, **kw: c.markets.status(use_human_readable=True, **kw),
    ),
    "options.expirations": Case(
        "options_expirations_response_200",
        f"{API}/v1/options/expirations/AAPL/",
        lambda c, **kw: c.options.expirations("AAPL", **kw),
    ),
    "options.lookup": Case(
        "options_lookup_response_200",
        f"{API}/v1/options/lookup/AAPL%2028-00-2023%20200.0%20call/",
        lambda c, **kw: c.options.lookup("AAPL 28-00-2023 200.0 call", **kw),
    ),
    "stocks.news": Case(
        "stocks_news_response_200",
        f"{API}/v1/stocks/news/AAPL/",
        lambda c, **kw: c.stocks.news("AAPL", **kw),
    ),
    "utilities.status": Case(
        "utilities_status_response_200",
        f"{API}/status/",
        lambda c, **kw: c.utilities.status(**kw),
    ),
    "utilities.headers": Case(
        "utilities_headers_response_200",
        f"{API}/headers/",
        lambda c, **kw: c.utilities.headers(**kw),
    ),
    "utilities.user": Case(
        "utilities_user_response_200",
        f"{API}/user/",
        lambda c, **kw: c.utilities.user(**kw),
    ),
    "options.expirations human": Case(
        "options_expirations_human_response_200",
        f"{API}/v1/options/expirations/AAPL/",
        lambda c, **kw: c.options.expirations("AAPL", use_human_readable=True, **kw),
    ),
    "stocks.news human": Case(
        "stocks_news_human_response_200",
        f"{API}/v1/stocks/news/AAPL/",
        lambda c, **kw: c.stocks.news("AAPL", use_human_readable=True, **kw),
    ),
}

OTHER_DATE_KEYS = {
    "markets.status": ("date",),
    "markets.status human": ("Date",),
    "options.expirations": ("expirations", "updated"),
    "options.expirations human": ("Expirations", "Date"),
    "stocks.news": ("publicationDate", "updated"),
    "stocks.news human": ("publicationDate", "Date"),
    "utilities.status": ("updated",),
}


def _load_fixture(name: str) -> dict:
    path = DATA_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _respond(
    respx_mock,
    case: Case,
    body: bytes | None = None,
    content_type: str | None = "application/json",
) -> None:
    """Answer every request to a case's URL with one body.

    Args:
        respx_mock: The router.
        case: The resource.
        body: The body; the case's fixture as JSON when omitted.
        content_type: The ``Content-Type`` header, or ``None`` for none.
    """
    if body is None:
        body = json.dumps(_load_fixture(case.fixture)).encode()
    headers = {"content-type": content_type} if content_type else {}
    respx_mock.get(case.url).respond(content=body, headers=headers)


def _holds_decimal(value) -> bool:
    if isinstance(value, Decimal):
        return True
    if isinstance(value, dict):
        return any(_holds_decimal(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_holds_decimal(item) for item in value)
    return False


def _money_holds_decimals_and_nothing_else(result) -> int:
    """Walk an INTERNAL result: every money value is a Decimal, no other field
    holds one, and a field annotated `int` (a size, a count, a day) holds
    ints, as the plain parse gives them. Returns how many money values it
    checked."""
    checked = 0
    for model in result if isinstance(result, list) else [result]:
        hints = typing.get_type_hints(type(model))
        money = decimal_fields(type(model))
        for name, value in vars(model).items():
            values = value if isinstance(value, list) else [value]
            present = [item for item in values if item is not None]
            if name in money:
                assert all(isinstance(item, Decimal) for item in present), name
                checked += len(present)
                continue
            assert not _holds_decimal(value), name
            if name in hints and _mentions(hints[name], int):
                assert all(type(item) is int for item in present), name
    return checked


def _mentions(annotation, target: type) -> bool:
    return annotation is target or any(
        _mentions(arg, target) for arg in typing.get_args(annotation)
    )


def _dates_in(result) -> list:
    """Every value of every date-annotated field of an INTERNAL result."""
    dates = []
    for model in result if isinstance(result, list) else [result]:
        hints = typing.get_type_hints(type(model))
        for field in dataclasses.fields(model):
            hint = hints[field.name]
            if _mentions(hint, datetime.datetime) or _mentions(hint, datetime.date):
                value = getattr(model, field.name)
                dates.extend(value if isinstance(value, list) else [value])
    return dates


def _all_models() -> set[type]:
    models = set()
    for info in pkgutil.iter_modules(marketdata.output_types.__path__):
        module = importlib.import_module(f"marketdata.output_types.{info.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if dataclasses.is_dataclass(obj) and obj.__module__ == module.__name__:
                models.add(obj)
    return models


# ------------------------------------------------------------ which fields


@pytest.mark.parametrize(
    "model", sorted(_all_models(), key=lambda m: m.__name__), ids=lambda m: m.__name__
)
def test_the_money_fields_are_the_ones_issue_50_lists(model):
    """Every model is here: one with money holds exactly the fields #50 names,
    and every other model, greeks, IV and percentages included, holds none."""
    assert decimal_fields(model) == frozenset(MONEY_FIELDS.get(model, ()))


# ----------------------------------------------------- the INTERNAL models


@pytest.mark.parametrize("case", MONEY_CASES.values(), ids=MONEY_CASES.keys())
def test_an_amount_reaches_the_model_with_every_digit_the_api_wrote(
    respx_mock, client, case
):
    """The float parse would read this value as 65.1 and no later conversion
    could bring the rest back, so a model holding it proves the INTERNAL path
    of this resource never parsed its money as a float."""
    data = _load_fixture(case.fixture)
    data[case.column][0] = "__exact__"
    body = json.dumps(data).replace('"__exact__"', EXACT).encode()
    _respond(respx_mock, case, body)

    result = case.call(client, output_format=OutputFormat.INTERNAL)

    assert case.read(result) == Decimal(EXACT)
    assert str(case.read(result)) == EXACT


@pytest.mark.parametrize("case", MONEY_CASES.values(), ids=MONEY_CASES.keys())
def test_money_is_decimal_and_every_other_number_keeps_its_type(
    respx_mock, client, case
):
    """The exact parse makes every number with a fraction a Decimal, money or
    not: an IV of `0.0`, a theta, a percentage. The model gives those back
    their floats, so a Decimal is found where the annotation says money and
    nowhere else."""
    _respond(respx_mock, case)

    result = case.call(client, output_format=OutputFormat.INTERNAL)

    assert _money_holds_decimals_and_nothing_else(result) > 0


@pytest.mark.parametrize("case", OTHER_CASES.values(), ids=OTHER_CASES.keys())
def test_a_resource_with_no_money_returns_no_decimal(respx_mock, client, case):
    _respond(respx_mock, case)

    result = case.call(client, output_format=OutputFormat.INTERNAL)

    assert not _holds_decimal(
        [vars(model) for model in (result if isinstance(result, list) else [result])]
    )


@pytest.mark.parametrize("name", OTHER_DATE_KEYS)
def test_a_resource_with_no_money_reads_a_spreadsheet_date(respx_mock, client, name):
    """Its models have no conversion, so they read a date only if the parse
    left it a float. This is the test that fails if one of them is ever
    switched to the exact parse. options.lookup, utilities.headers and
    utilities.user carry no number with a fraction, so the parse they use
    cannot be told apart."""
    case = OTHER_CASES[name]
    data = _load_fixture(case.fixture)
    for key in OTHER_DATE_KEYS[name]:
        assert key in data, key
        data[key] = (
            ["__date__"] * len(data[key]) if isinstance(data[key], list) else "__date__"
        )
    body = json.dumps(data).replace('"__date__"', SPREADSHEET_DATE).encode()
    _respond(respx_mock, case, body)

    result = case.call(client, output_format=OutputFormat.INTERNAL)

    dates = _dates_in(result)
    assert dates
    assert all(date == SPREADSHEET_DATETIME for date in dates)


def test_a_greek_is_the_float_the_plain_parse_gives(respx_mock, client):
    """Bit for bit: `float(Decimal(text))` reads the Decimal's own digits."""
    case = MONEY_CASES["options.quotes"]
    _respond(respx_mock, case)
    plain = _load_fixture(case.fixture)

    quotes = case.call(client, output_format=OutputFormat.INTERNAL)

    for greek in ("iv", "delta", "gamma", "theta", "vega"):
        value = getattr(quotes, greek)[0]
        assert type(value) is float, greek
        assert value.hex() == float(plain[greek][0]).hex(), greek


@pytest.mark.parametrize("case", MONEY_CASES.values(), ids=MONEY_CASES.keys())
def test_a_whole_number_amount_is_a_decimal_too(respx_mock, client, case):
    """A JSON integer never goes through `parse_float`: a price of `110`
    arrives as an int, and only the model's own conversion makes it a Decimal.
    That makes this the test that notices a model without it."""
    data = _load_fixture(case.fixture)
    data[case.column][0] = 110
    _respond(respx_mock, case, json.dumps(data).encode())

    result = case.call(client, output_format=OutputFormat.INTERNAL)

    assert case.read(result) == Decimal("110")
    assert type(case.read(result)) is Decimal


def test_a_spread_is_exact(respx_mock, client):
    """What #50 is for: `0.3 - 0.1` is not `0.2` in binary floating point."""
    respx_mock.get(f"{API}/v1/stocks/quotes/").respond(
        content=(
            b'{"s": "ok", "symbol": ["AAPL"], "ask": [0.3], "askSize": [1], '
            b'"bid": [0.1], "bidSize": [1], "mid": [0.2], "last": [0.2], '
            b'"change": [0.0], "changepct": [0.0], "volume": [1], '
            b'"updated": [1765478200]}'
        ),
        headers={"content-type": "application/json"},
    )

    quote = client.stocks.quotes("AAPL", output_format=OutputFormat.INTERNAL)[0]

    assert 0.3 - 0.1 != 0.2
    assert quote.ask - quote.bid == Decimal("0.2") == quote.mid


# One price row whose `mid` is the bytes given.
PRICE_BODY = (
    b'{"s": "ok", "symbol": ["AAPL"], "mid": [%s], '
    b'"change": [0.1], "changepct": [0.01], "updated": [1765478200]}'
)


def _respond_price(respx_mock, mid: bytes) -> None:
    respx_mock.get(f"{API}/v1/stocks/prices/").respond(
        content=PRICE_BODY % mid, headers={"content-type": "application/json"}
    )


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize(
    "output_format",
    [OutputFormat.INTERNAL, OutputFormat.JSON, OutputFormat.DATAFRAME],
    ids=["internal", "json", "dataframe"],
)
def test_a_non_finite_literal_fails_the_call_on_every_decoded_format(
    respx_mock, client, literal, output_format
):
    """`NaN` and `Infinity` are not JSON, yet Python's decoder reads them. The
    API's renderer refuses them (the call answers 500), so one in a body was
    written by something in between, and no price, greek or date is one. On
    main every format returned them as `nan` and `inf`. With money exact, the
    model first held `None` for a NaN, which reads as a price the API does
    not have, and refused an infinity, while the other formats still returned
    both: the format decided whether the call raised (#50 review). The body
    fails before any DataFrame handler runs, so the library does not matter."""
    _respond_price(respx_mock, literal.encode())

    with pytest.raises(ParseError) as failure:
        client.stocks.prices("AAPL", output_format=output_format)

    assert failure.value.message.startswith(
        f"Response body has a number that is not finite ({literal}): "
    )


def test_a_resource_that_writes_its_csv_from_the_decoded_body_refuses_it_too(
    respx_mock, client
):
    """`client.utilities` decodes the body for every format and builds its CSV
    from it, so its CSV output is a decoded format like the other three (#50
    review)."""
    case = OTHER_CASES["utilities.status"]
    data = _load_fixture(case.fixture)
    data["uptimePct30d"][0] = "__nan__"
    _respond(respx_mock, case, json.dumps(data).replace('"__nan__"', "NaN").encode())

    with pytest.raises(ParseError) as failure:
        case.call(client, output_format=OutputFormat.CSV)

    assert failure.value.message.startswith(
        "Response body has a number that is not finite (NaN): "
    )


def test_a_csv_file_is_the_api_text_whatever_numbers_it_carries(
    respx_mock, client, tmp_path
):
    """The fourth format decodes no number: the file is the API's text as it
    came, so there is nothing in it for the SDK to refuse (#50 review)."""
    body = "s,symbol,mid\r\nok,AAPL,NaN\r\n"
    respx_mock.get(f"{API}/v1/stocks/prices/").respond(text=body)

    path = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename=tmp_path / "prices.csv"
    )

    assert pathlib.Path(path).read_bytes() == body.encode()


@pytest.mark.parametrize(
    "number, internal",
    [(b"1e400", Decimal("1E+400")), (b"1e9999999999999999999", ParseError)],
    ids=["past a float", "past a decimal"],
)
def test_a_number_past_what_a_float_holds_is_a_documented_difference(
    respx_mock, client, number, internal
):
    """The plain parse reads both as `inf`. The exact parse keeps the first
    and refuses the second, which no `Decimal` can hold. The formats differ
    here on purpose: refusing these on the plain parse would take a hook on
    every number, which made the decode about 1.4 to 1.9 times slower on
    bodies of about 50 000 numbers, for a body the renderer behind the API's
    data endpoints does not write, since it prints a float by its shortest
    repr, whose exponent stops at 308 (#50 review). Pinned, so that changing
    it is a decision."""
    _respond_price(respx_mock, number)

    if internal is ParseError:
        with pytest.raises(ParseError) as failure:
            client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)
        assert failure.value.message.startswith(
            "Response body has a number out of range: "
        )
    else:
        mid = client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)[0].mid
        assert str(mid) == str(internal)
    body = client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    assert body["mid"] == [math.inf]
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        frame = client.stocks.prices("AAPL", output_format=OutputFormat.DATAFRAME)
    assert frame["mid"].tolist() == [math.inf]


@pytest.mark.parametrize(
    "raw, decoded, refusal",
    [
        (b'"n/a"', "n/a", "not a decimal number: 'n/a'"),
        (b"true", True, "an amount cannot be a bool: True"),
        (b'"NaN"', "NaN", "an amount must be finite, not 'NaN'"),
    ],
    ids=["a word", "a boolean", "a string nan"],
)
def test_a_value_the_model_cannot_hold_is_a_parse_error_not_a_builtin(
    respx_mock, client, raw, decoded, refusal
):
    """The model refuses a value that is not an amount, and on the API path
    that refusal has to be an SDK exception: a caller who wrote
    `except BaseMarketdataException` does not catch a `TypeError` (#91, #50
    review). Only a typed model reads the value, so only it can refuse one:
    the JSON output returns the body as decoded, as it always did."""
    _respond_price(respx_mock, raw)

    with pytest.raises(ParseError) as failure:
        client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)

    # The body excerpt holds `mid` too, so the field is checked through the
    # text only the model's refusal carries.
    assert f"(StockPrice.mid: {refusal}): " in failure.value.message
    body = client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    assert body["mid"] == [decoded]


@pytest.mark.parametrize(
    "name", ["options.expirations", "markets.status", "utilities.user"]
)
def test_a_body_missing_a_column_the_model_needs_is_a_parse_error(
    respx_mock, client, name
):
    """A column the model needs and the body lacks is refused with an SDK
    exception, not a bare `TypeError` from the model's constructor."""
    case = OTHER_CASES[name]
    data = _load_fixture(case.fixture)
    del data[next(key for key in data if key != "s")]
    _respond(respx_mock, case, json.dumps(data).encode())

    with pytest.raises(ParseError) as failure:
        case.call(client, output_format=OutputFormat.INTERNAL)

    message = failure.value.message
    assert message.startswith("Response body is not a valid answer of this resource (")
    assert "missing 1 required positional argument" in message


# Every INTERNAL resource whose answer is built into a model through its
# columns: `utilities.headers` keeps every key as a header, and
# `utilities.user` reads only the keys it knows.
MODEL_CASES = {
    name: case
    for name, case in {**MONEY_CASES, **OTHER_CASES}.items()
    if name not in ("utilities.headers", "utilities.user")
}


def _undeclared_columns_logged(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if "does not declare" in record.getMessage()
    ]


def _add_new_column(data: dict) -> list[str] | str:
    """Add a column no model declares to an API answer.

    Args:
        data: The answer, keyed by column name; changed in place.

    Returns:
        The column's value: one text per row when the answer's first column
        is a list, one text otherwise.
    """
    first = data[next(key for key in data if key != "s")]
    data["brandNew"] = (
        [f"new {index}" for index in range(len(first))]
        if isinstance(first, list)
        else "new"
    )
    return data["brandNew"]


@pytest.mark.parametrize("name", MODEL_CASES)
def test_a_column_no_model_declares_is_kept_for_get_extra(
    respx_mock, client, caplog, name
):
    """A column the API adds before the model declares it does not break the
    call: the fields are the ones the answer builds without it, ``get_extra``
    holds the column, a row its own value, and the column is named once at
    DEBUG however many rows the answer has, the fan-outs' merged answer
    included."""
    case = MODEL_CASES[name]
    data = _load_fixture(case.fixture)
    _respond(respx_mock, case, json.dumps(data).encode())
    with caplog.at_level("DEBUG", logger="marketdata.logger"):
        expected = case.call(client, output_format=OutputFormat.INTERNAL)
    assert _undeclared_columns_logged(caplog) == []

    column = _add_new_column(data)
    _respond(respx_mock, case, json.dumps(data).encode())
    caplog.clear()
    with caplog.at_level("DEBUG", logger="marketdata.logger"):
        result = case.call(client, output_format=OutputFormat.INTERNAL)

    assert result == expected
    models = result if isinstance(result, list) else [result]
    extras = [marketdata.get_extra(model) for model in models]
    if isinstance(result, list) and isinstance(column, list):
        assert extras == [{"brandNew": value} for value in column]
    else:
        assert extras == [{"brandNew": column}] * len(models)
    assert _undeclared_columns_logged(caplog) == [
        f"The API sent the columns ['brandNew'], which {type(models[0]).__name__}"
        " does not declare; get_extra() holds them"
    ]


@pytest.mark.parametrize("name", MODEL_CASES)
def test_a_column_no_model_declares_reaches_every_format(
    respx_mock, client, tmp_path, name
):
    """An answer with a column the model does not declare carries it on every
    format, the fan-outs' merge included: INTERNAL through ``get_extra``, JSON
    and DataFrame as a column, and CSV in the file, which is the API's text
    or, on the utilities, the file written from the decoded answer."""
    case = MODEL_CASES[name]
    data = _load_fixture(case.fixture)
    _add_new_column(data)
    _respond(respx_mock, case, json.dumps(data).encode())

    result = case.call(client, output_format=OutputFormat.INTERNAL)
    as_json = case.call(client, output_format=OutputFormat.JSON)
    frame = case.call(client, output_format=OutputFormat.DATAFRAME)
    if not name.startswith("utilities."):
        first = next(key for key in data if key != "s")
        _respond(respx_mock, case, f"{first},brandNew\r\nx,new 0\r\n".encode())
    path = case.call(
        client, output_format=OutputFormat.CSV, filename=tmp_path / "answer.csv"
    )

    models = result if isinstance(result, list) else [result]
    assert all("brandNew" in marketdata.get_extra(model) for model in models)
    assert as_json["brandNew"] == data["brandNew"]
    assert "brandNew" in frame.columns
    header = pathlib.Path(path).read_text(encoding="utf-8").splitlines()[0]
    assert "brandNew" in header.split(",")


def test_an_undeclared_value_that_is_not_a_list_goes_to_every_row(respx_mock, client):
    """A column the model does not declare that holds one value instead of a
    list gives that value to every row, on every format that decodes it."""
    case = MODEL_CASES["funds.candles"]
    data = _load_fixture(case.fixture)
    data["brandNew"] = "new"
    _respond(respx_mock, case, json.dumps(data).encode())

    rows = case.call(client, output_format=OutputFormat.INTERNAL)
    as_json = case.call(client, output_format=OutputFormat.JSON)
    frame = case.call(client, output_format=OutputFormat.DATAFRAME)

    assert [marketdata.get_extra(row) for row in rows] == [{"brandNew": "new"}] * 7
    assert as_json["brandNew"] == "new"
    assert list(frame["brandNew"]) == ["new"] * 7


def _list_columns(data: dict) -> list[str]:
    """Name the keys of a decoded answer that hold a list, but ``s``.

    Args:
        data: The decoded answer.

    Returns:
        The keys, in the answer's order.
    """
    return [
        key for key, value in data.items() if key != "s" and isinstance(value, list)
    ]


def _parse_errors_on_decoded_formats(
    client, case: Case, path: pathlib.Path
) -> set[str]:
    """Call a resource on every format that decodes its answer.

    Args:
        client: The client.
        case: The resource.
        path: The file ``utilities.status`` writes its CSV to, from the decoded
            answer.

    Returns:
        The messages of the ``ParseError`` each call raised.
    """
    calls = [
        {"output_format": OutputFormat.INTERNAL},
        {"output_format": OutputFormat.JSON},
        {"output_format": OutputFormat.DATAFRAME},
    ]
    if case is MODEL_CASES["utilities.status"]:
        calls.append({"output_format": OutputFormat.CSV, "filename": path})
    messages = set()
    for kwargs in calls:
        with pytest.raises(ParseError) as failure:
            case.call(client, **kwargs)
        messages.add(failure.value.message)
    return messages


UNEVEN_CASES = [name for name in MODEL_CASES if name != "options.lookup"]
SHORT_CASES = [name for name in UNEVEN_CASES if "expirations" not in name]


@pytest.mark.parametrize("name", UNEVEN_CASES)
def test_an_undeclared_list_of_another_length_is_a_parse_error_on_every_format(
    respx_mock, client, tmp_path, name
):
    """A column the model does not declare whose list has one value more than
    the rows raises one ``ParseError`` on INTERNAL, JSON and DataFrame, and on
    the CSV ``utilities.status`` writes from the decoded answer."""
    case = MODEL_CASES[name]
    data = _load_fixture(case.fixture)
    rows = len(data[_list_columns(data)[0]])
    data["brandNew"] = list(range(rows + 1))
    _respond(respx_mock, case, json.dumps(data).encode())

    messages = _parse_errors_on_decoded_formats(client, case, tmp_path / "a.csv")

    assert len(messages) == 1
    message = messages.pop()
    assert "(columns of different lengths {" in message
    assert f"'brandNew': {rows + 1}}})" in message


@pytest.mark.parametrize("name", SHORT_CASES)
def test_a_declared_column_of_another_length_is_a_parse_error_on_every_format(
    respx_mock, client, tmp_path, name
):
    """A column the model declares that is one value short of the others
    raises one ``ParseError`` on INTERNAL, JSON and DataFrame, and on the CSV
    ``utilities.status`` writes from the decoded answer."""
    case = MODEL_CASES[name]
    data = _load_fixture(case.fixture)
    first = _list_columns(data)[0]
    rows = len(data[first])
    data[first] = data[first][:-1]
    _respond(respx_mock, case, json.dumps(data).encode())

    messages = _parse_errors_on_decoded_formats(client, case, tmp_path / "a.csv")

    assert len(messages) == 1
    message = messages.pop()
    assert "(columns of different lengths {" in message
    assert f"{first!r}: {rows - 1}" in message


def test_get_extra_is_empty_for_an_object_with_no_dict():
    """``get_extra`` finds nothing on an object that has no ``__dict__`` to
    hold an undeclared column."""
    assert marketdata.get_extra(None) == {}
    assert marketdata.get_extra(object()) == {}


@pytest.mark.parametrize("name", MODEL_CASES)
def test_an_object_with_none_of_the_model_columns_is_a_parse_error(
    respx_mock, client, name
):
    """An object that carries none of the model's columns, like a proxy's JSON
    error page, is not an answer of this resource, so no row is built from
    what is left of it."""
    case = MODEL_CASES[name]
    _respond(respx_mock, case, json.dumps({"error": "upstream timeout"}).encode())

    with pytest.raises(ParseError) as failure:
        case.call(client, output_format=OutputFormat.INTERNAL)

    assert failure.value.message.startswith(
        "Response body is not a valid answer of this resource ("
    )


SINGLE_OBJECT_MODEL_CASES = [
    "options.chain",
    "options.chain human",
    "options.expirations",
    "options.expirations human",
    "options.lookup",
    "stocks.earnings",
    "stocks.earnings human",
]


@pytest.mark.parametrize("name", SINGLE_OBJECT_MODEL_CASES)
def test_a_foreign_object_is_a_parse_error_on_every_format(
    respx_mock, client, tmp_path, name
):
    """A single-object resource refuses a JSON object that carries none of its
    columns, like a proxy's JSON error page, on every format: the same
    ``ParseError`` on the three that decode it, and on CSV the one a header
    with none of the resource's columns gets or, without a header row, the one
    a body that reads as JSON gets."""
    case = MODEL_CASES[name]
    text = json.dumps({"error": "upstream timeout"})
    _respond(respx_mock, case, text.encode())

    messages = set()
    for output_format in (
        OutputFormat.INTERNAL,
        OutputFormat.JSON,
        OutputFormat.DATAFRAME,
    ):
        with pytest.raises(ParseError) as failure:
            case.call(client, output_format=output_format)
        messages.add(failure.value.message)
    with pytest.raises(ParseError) as refused:
        case.call(
            client, output_format=OutputFormat.CSV, filename=tmp_path / "answer.csv"
        )
    with pytest.raises(ParseError) as headerless:
        case.call(
            client,
            output_format=OutputFormat.CSV,
            add_headers=False,
            filename=tmp_path / "answer.csv",
        )

    assert messages == {
        "Response body is not a valid answer of this resource (none of this"
        f" resource's fields): {text!r}"
    }
    assert refused.value.message == (
        "Response body is not a valid answer of this resource (unknown columns"
        f" [{text!r}]): {text!r}"
    )
    assert "(JSON or HTML, not CSV)" in headerless.value.message
    assert not (tmp_path / "answer.csv").exists()


@pytest.mark.parametrize("body", [b"[1]", b"null", b'"x"', b"5", b"true"])
@pytest.mark.parametrize("name", SINGLE_OBJECT_MODEL_CASES)
def test_a_body_that_is_not_an_object_is_a_parse_error_on_every_format(
    respx_mock, client, tmp_path, name, body
):
    """A single-object resource refuses a JSON answer that is not an object on
    every format, under the API's names and the human-readable ones: the same
    ``ParseError`` on the three that decode it, and on CSV the one a header
    with none of the resource's columns gets or, without a header row, the one
    a JSON answer gets."""
    case = MODEL_CASES[name]
    _respond(respx_mock, case, body)

    messages = set()
    for output_format in (
        OutputFormat.INTERNAL,
        OutputFormat.JSON,
        OutputFormat.DATAFRAME,
    ):
        with pytest.raises(ParseError) as failure:
            case.call(client, output_format=output_format)
        messages.add(failure.value.message)
    with pytest.raises(ParseError) as refused:
        case.call(
            client, output_format=OutputFormat.CSV, filename=tmp_path / "answer.csv"
        )
    with pytest.raises(ParseError) as headerless:
        case.call(
            client,
            output_format=OutputFormat.CSV,
            add_headers=False,
            filename=tmp_path / "answer.csv",
        )

    text = body.decode()
    header = next(csv.reader([text]))
    assert messages == {
        "Response body is not a valid answer of this resource (not a JSON object):"
        f" {text!r}"
    }
    assert refused.value.message == (
        "Response body is not a valid answer of this resource (unknown columns"
        f" {header!r}): {text!r}"
    )
    assert headerless.value.message == (
        "Response body is not a valid answer of this resource (JSON or HTML, not"
        f" CSV): {text!r}"
    )
    assert not (tmp_path / "answer.csv").exists()


SINGLE_OBJECT_CASES = [
    "options.chain",
    "options.expirations",
    "options.lookup",
    "stocks.earnings",
]
FAN_OUT_CASES = ["stocks.candles", "options.quotes"]


@pytest.mark.parametrize(
    "body", [b"AAPL,200\r\n", b"1790740800\r\n"], ids=["a row", "one cell"]
)
@pytest.mark.parametrize("name", SINGLE_OBJECT_CASES + FAN_OUT_CASES)
def test_a_csv_without_a_header_row_is_written_as_it_came(
    respx_mock, client, tmp_path, name, body
):
    """Under ``add_headers=False`` an answer labeled CSV has no header row to
    check, so the file is the API's text as it came, a lone number that also
    reads as JSON included."""
    case = MODEL_CASES[name]
    _respond(respx_mock, case, body, "text/csv; charset=utf-8")

    path = case.call(
        client,
        output_format=OutputFormat.CSV,
        add_headers=False,
        filename=tmp_path / "answer.csv",
    )

    assert pathlib.Path(path).read_bytes() == body


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b'{"error": "upstream timeout"}', None),
        (b"<html><body>502 Bad Gateway</body></html>", "text/plain; charset=utf-8"),
        (b"502 Bad Gateway", "text/html; charset=utf-8"),
        (b'"x"', "application/problem+json"),
    ],
    ids=[
        "a JSON object, unlabeled",
        "an HTML page labeled text",
        "text labeled HTML",
        "a string labeled problem+json",
    ],
)
def test_a_headerless_csv_that_reads_as_json_or_html_is_a_parse_error(
    respx_mock, client, tmp_path, body, content_type
):
    """Under ``add_headers=False`` an answer labeled JSON or HTML, or whose
    body reads as either under another label or none, is not a CSV answer, so
    it is refused and no file is written."""
    case = MODEL_CASES["options.chain"]
    _respond(respx_mock, case, body, content_type)

    with pytest.raises(ParseError) as refused:
        case.call(
            client,
            output_format=OutputFormat.CSV,
            add_headers=False,
            filename=tmp_path / "answer.csv",
        )

    assert "(JSON or HTML, not CSV)" in refused.value.message
    assert not (tmp_path / "answer.csv").exists()


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b"[1]", None),
        (b'"x"', "application/json"),
        (b"5", "application/json"),
        (b"true", "application/json"),
    ],
    ids=["a list, unlabeled", "a string", "a number", "a boolean"],
)
@pytest.mark.parametrize("name", FAN_OUT_CASES)
def test_a_fan_out_headerless_csv_that_reads_as_json_is_a_parse_error(
    respx_mock, client, tmp_path, name, body, content_type
):
    """The fan-outs' merge refuses a headerless answer labeled JSON, or whose
    body reads as JSON under no label, as their JSON output refuses a body
    that is not an object."""
    case = MODEL_CASES[name]
    _respond(respx_mock, case, body, content_type)

    with pytest.raises(ParseError) as refused:
        case.call(
            client,
            output_format=OutputFormat.CSV,
            add_headers=False,
            filename=tmp_path / "answer.csv",
        )
    with pytest.raises(ParseError) as decoded:
        case.call(client, output_format=OutputFormat.JSON)

    assert "(JSON or HTML, not CSV)" in refused.value.message
    assert "(not a JSON object)" in decoded.value.message
    assert not (tmp_path / "answer.csv").exists()


def test_get_extra_survives_copy_and_pickle(respx_mock, client):
    """The columns a model does not declare live on the model itself, so a
    copy, a deep copy and a pickled model keep them."""
    case = MODEL_CASES["stocks.quotes"]
    data = _load_fixture(case.fixture)
    _add_new_column(data)
    _respond(respx_mock, case, json.dumps(data).encode())

    quote = case.call(client, output_format=OutputFormat.INTERNAL)[0]

    for twin in (
        copy.copy(quote),
        copy.deepcopy(quote),
        pickle.loads(pickle.dumps(quote)),
    ):
        assert marketdata.get_extra(twin) == {"brandNew": "new 0"}


def test_a_csv_header_the_csv_module_cannot_read_is_a_parse_error(
    respx_mock, client, tmp_path
):
    """A header past the ``csv`` module's field size limit cannot be read, so
    the answer is refused and no file is written."""
    case = MODEL_CASES["options.chain"]
    _respond(respx_mock, case, b"x" * (csv.field_size_limit() + 1))

    with pytest.raises(ParseError) as refused:
        case.call(
            client, output_format=OutputFormat.CSV, filename=tmp_path / "answer.csv"
        )

    assert refused.value.message.startswith(
        "Response body is not a valid answer of this resource (unreadable CSV: "
    )
    assert not (tmp_path / "answer.csv").exists()


@pytest.mark.parametrize("name", OTHER_DATE_KEYS.keys())
def test_a_date_the_model_cannot_read_is_a_parse_error_with_no_money_involved(
    respx_mock, client, name
):
    """The refusal of a model is an SDK exception on every resource, not only
    on the ones with money: a date the model cannot read used to escape these
    as a bare `ValueError` (#50 review)."""
    case = OTHER_CASES[name]
    data = _load_fixture(case.fixture)
    data[OTHER_DATE_KEYS[name][0]][0] = "not a date"
    _respond(respx_mock, case, json.dumps(data).encode())

    with pytest.raises(ParseError) as failure:
        case.call(client, output_format=OutputFormat.INTERNAL)

    assert "(Unrecognized date format): " in failure.value.message
    assert failure.value.request_url.startswith(case.url)


def _answer(url: str) -> httpx.Response:
    return httpx.Response(200, text=url, request=httpx.Request("GET", url))


@pytest.mark.parametrize(
    "refusing, named, reason",
    [
        (("a", "b"), "a", "a refused alone"),
        (("b",), "b", "b refused alone"),
        ((), "b", "refused merged"),
    ],
    ids=["both, the first", "the last alone", "none alone, the last"],
)
def test_a_merged_refusal_names_the_first_answer_refused_alone(refusing, named, reason):
    """Each answer is built again on its own, in request order, and the first
    one refused is named with its own reason, whatever the exception. A
    refusal no answer produces alone could only come from the merge, which no
    model does today; the last answer is named then, with the merge's reason,
    rather than none (#50 review)."""
    answers = [_answer(f"{API}/{key}/") for key in ("a", "b")]

    def build_alone(answer):
        key = str(answer.request.url).rstrip("/")[-1]
        if key in refusing:
            raise (ValueError if key == "a" else LookupError)(f"{key} refused alone")

    with pytest.raises(ParseError) as failure:
        with merged_model_errors(answers, build_alone):
            raise TypeError("refused merged")

    assert failure.value.request_url == f"{API}/{named}/"
    assert f"({reason}): " in failure.value.message
    assert str(failure.value.__cause__) == reason


@pytest.mark.parametrize("trapped", [True, False])
def test_the_parse_does_not_depend_on_the_caller_decimal_traps(
    respx_mock, client, trapped
):
    """Whether an unreadable number raises or decodes as NaN is a trap on a
    thread-local context the caller owns, and finance code turns it off. With
    it off, `"n/a"` used to arrive as NaN and leave as `None`, which reads as
    a price the API does not have (#50 review)."""
    with localcontext() as context:
        context.traps[InvalidOperation] = trapped

        with pytest.raises(ValueError, match="not a decimal number"):
            to_decimal("n/a")

        respx_mock.get(f"{API}/v1/stocks/prices/").respond(
            content=(
                b'{"s": "ok", "symbol": ["AAPL"], "mid": [1e9999999999999999999], '
                b'"change": [0.1], "changepct": [0.01], "updated": [1765478200]}'
            ),
            headers={"content-type": "application/json"},
        )
        with pytest.raises(ParseError, match="out of range"):
            client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)


@pytest.mark.parametrize(
    "container",
    [
        np.array([100.0, 105.0]),
        pd.Series([100.0, 105.0]),
        pl.Series([100.0, 105.0]),
    ],
    ids=["ndarray", "pandas", "polars"],
)
def test_an_array_in_a_money_field_is_left_as_it_came(container):
    """A model rebuilt from the columns of a DataFrame holds an ndarray or a
    Series in a money field. Converting it would hand back a different
    container and rejecting it would break code that worked before money was
    exact, so it is left alone, as the plain parse left it (#50 review)."""
    fields = {field.name: [] for field in dataclasses.fields(OptionsChain)}

    chain = OptionsChain(**{**fields, "s": "ok", "strike": container})

    assert chain.strike is container


def test_a_numpy_string_is_a_string():
    """It hands numpy its value and has a length, as an array does, and is
    still read as the string it is (#50 review)."""
    fields = {field.name: [] for field in dataclasses.fields(OptionsChain)}

    chain = OptionsChain(**{**fields, "s": "ok", "strike": np.str_("65.1")})

    assert type(chain.strike) is Decimal
    assert str(chain.strike) == "65.1"
    with pytest.raises(TypeError):
        OptionsChain(**{**fields, "s": "ok", "strike": np.bytes_(b"65.1")})


@pytest.mark.parametrize(
    "container",
    [
        {"strike": 100.0},
        {100.0},
        (strike for strike in [100.0]),
        range(2),
        array.array("d", [100.0]),
    ],
    ids=["dict", "set", "generator", "range", "array.array"],
)
def test_a_container_that_is_not_an_array_is_not_an_amount(container):
    """Only an array is left as it came. Anything else in a money field is a
    value that is not an amount, and a generator would otherwise have been
    stored unconsumed (#50 review)."""
    fields = {field.name: [] for field in dataclasses.fields(OptionsChain)}

    with pytest.raises(TypeError) as refusal:
        OptionsChain(**{**fields, "s": "ok", "strike": container})

    assert str(refusal.value) == (
        "OptionsChain.strike: an amount must be a number, "
        f"not {type(container).__name__}"
    )


# ------------------------------ dates the exact parse would have broken


def test_every_money_case_lists_its_dates():
    assert DATE_KEYS.keys() == MONEY_CASES.keys()


@pytest.mark.parametrize("name", MONEY_CASES)
def test_a_spreadsheet_date_still_reads(respx_mock, client, name):
    """Under `dateformat=spreadsheet` a fractional date still formats as a datetime."""
    case = MONEY_CASES[name]
    data = _load_fixture(case.fixture)
    for key in DATE_KEYS[name]:
        assert key in data, key
        data[key] = (
            ["__date__"] * len(data[key]) if isinstance(data[key], list) else "__date__"
        )
    body = json.dumps(data).replace('"__date__"', SPREADSHEET_DATE).encode()
    _respond(respx_mock, case, body)

    result = case.call(client, output_format=OutputFormat.INTERNAL)

    dates = _dates_in(result)
    assert dates
    assert all(date == SPREADSHEET_DATETIME for date in dates)


def _with_null_dates(name: str) -> tuple[Case, dict]:
    """Load the fixture of `name` with the first value of each date key set to null.

    A key that holds a single date is set to null whole. Returns the case and
    the body.
    """
    case = MONEY_CASES.get(name) or OTHER_CASES[name]
    data = _load_fixture(case.fixture)
    for key in DATE_KEYS.get(name) or OTHER_DATE_KEYS[name]:
        if isinstance(data[key], list):
            data[key][0] = None
        else:
            data[key] = None
    return case, data


def _internal_column(result, key: str) -> list:
    """The values an INTERNAL result holds for the body key `key`, row by row."""
    attribute = key.replace(" ", "_")
    if isinstance(result, list):
        return [getattr(model, attribute) for model in result]
    value = getattr(result, attribute)
    return value if isinstance(value, list) else [value]


def _output_name(names, key: str) -> str:
    """The name `key` goes by among `names`: as sent, or with underscores for
    spaces, as the merged `options.quotes` answer names it."""
    return key if key in names else key.replace(" ", "_")


def _frame_column(frame, key: str) -> list:
    """The values of the body key `key` in a pandas or polars DataFrame.

    A pandas frame may hold the key as its index rather than as a column.
    """
    if isinstance(frame, pl.DataFrame):
        return frame[_output_name(frame.columns, key)].to_list()
    name = _output_name([*frame.columns, frame.index.name], key)
    if name in frame.columns:
        return list(frame[name])
    assert frame.index.name == name, key
    return list(frame.index)


def _missing_where_sent_null(sent, read: list) -> bool:
    """Whether `read` is missing exactly where `sent` is null, row for row.

    A list keeps its length; a single date sent null reads as missing in every
    row it applies to.
    """
    if not isinstance(sent, list):
        return bool(read) and all(pd.isna(value) for value in read)
    return [pd.isna(value) for value in read] == [value is None for value in sent]


@pytest.mark.parametrize("name", [*DATE_KEYS, *OTHER_DATE_KEYS])
def test_a_null_date_is_none_on_every_internal_model(respx_mock, client, name):
    """The API answers `null` for a date it does not have. Every INTERNAL model
    keeps it as `None` in its own row, for every date key, and reads every
    other date of the key."""
    case, data = _with_null_dates(name)
    _respond(respx_mock, case, json.dumps(data).encode())

    result = case.call(client, output_format=OutputFormat.INTERNAL)

    for key in DATE_KEYS.get(name) or OTHER_DATE_KEYS[name]:
        read = _internal_column(result, key)
        assert _missing_where_sent_null(data[key], read), key
        assert all(
            isinstance(value, datetime.datetime) for value in read if value is not None
        ), key


@pytest.mark.parametrize("library", ["pandas", "polars", "json"])
@pytest.mark.parametrize("name", [*DATE_KEYS, *OTHER_DATE_KEYS])
def test_a_null_date_keeps_its_row_on_the_other_decoded_formats(
    respx_mock, client, name, library
):
    """The body that INTERNAL reads returns on JSON and on a DataFrame of either
    library too, each date key missing in the same row it was sent null in."""
    case, data = _with_null_dates(name)
    _respond(respx_mock, case, json.dumps(data).encode())

    if library == "json":
        result = case.call(client, output_format=OutputFormat.JSON)
    else:
        with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", [library]):
            result = case.call(client, output_format=OutputFormat.DATAFRAME)

    for key in DATE_KEYS.get(name) or OTHER_DATE_KEYS[name]:
        if library == "json":
            value = result[_output_name(result, key)]
            read = value if isinstance(value, list) else [value]
        else:
            read = _frame_column(result, key)
        assert _missing_where_sent_null(data[key], read), key


def test_a_null_date_keeps_its_row_in_a_csv_file(respx_mock, client, tmp_path):
    """The CSV file is the API's text: an empty date cell stays in its row."""
    body = (
        "t,o,h,l,c,v\r\n"
        "1577941200,74.06,75.15,73.7975,75.0875,135647456\r\n"
        ",74.2875,75.145,74.125,74.3575,146535512\r\n"
        "1578286800,73.4475,74.99,73.1875,74.95,118578576\r\n"
    )
    respx_mock.get(f"{API}/v1/stocks/candles/D/AAPL/").respond(text=body)

    path = client.stocks.candles(
        "AAPL",
        resolution="D",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "candles.csv",
    )

    assert pathlib.Path(path).read_bytes() == body.encode()


def test_a_null_date_keeps_its_row_in_a_merged_csv_file(respx_mock, client, tmp_path):
    """Three symbols merge into one file, and the middle symbol's empty
    `firstTraded` cell stays in its own row."""
    header = "optionSymbol,firstTraded,bid"
    rows = [
        "AAPL271217C00255000,1741872600,65.1",
        "AAPL271217P00255000,,1.2",
        "AAPL271217C00260000,1742045400,60.5",
    ]
    symbols = [row.split(",")[0] for row in rows]
    for symbol, row in zip(symbols, rows):
        respx_mock.get(f"{API}/v1/options/quotes/{symbol}/").respond(
            text=f"{header}\r\n{row}\r\n"
        )

    path = client.options.quotes(
        symbols, output_format=OutputFormat.CSV, filename=tmp_path / "quotes.csv"
    )

    assert pathlib.Path(path).read_bytes() == "\r\n".join([header, *rows, ""]).encode()


def test_a_null_date_is_an_empty_cell_in_a_csv_file_built_from_the_body(
    respx_mock, client, tmp_path
):
    """`client.utilities` writes its CSV from the decoded body: a null date
    is an empty cell in its own row."""
    case, data = _with_null_dates("utilities.status")
    _respond(respx_mock, case, json.dumps(data).encode())

    path = case.call(
        client, output_format=OutputFormat.CSV, filename=tmp_path / "status.csv"
    )

    rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    assert [row["updated"] == "" for row in rows] == [
        value is None for value in data["updated"]
    ]


def test_every_date_field_is_annotated_as_optional():
    """A `null` date reads as `None` on every model, so each date field's
    annotation admits `None`, per element for a column of dates."""
    checked, closed = 0, []
    for model in _all_models():
        hints = typing.get_type_hints(model)
        for field in dataclasses.fields(model):
            hint = hints[field.name]
            if not (
                _mentions(hint, datetime.datetime) or _mentions(hint, datetime.date)
            ):
                continue
            checked += 1
            element = (
                typing.get_args(hint)[0] if typing.get_origin(hint) is list else hint
            )
            if type(None) not in typing.get_args(element):
                closed.append(f"{model.__name__}.{field.name}")
    assert checked
    assert closed == []


# ------------------------------------------ the formats that keep floats


@pytest.mark.parametrize("case", MONEY_CASES.values(), ids=MONEY_CASES.keys())
def test_json_output_keeps_the_float_parse(respx_mock, client, case):
    _respond(respx_mock, case)

    result = case.call(client, output_format=OutputFormat.JSON)

    assert not _holds_decimal(result)
    assert type(result[case.column][0]) is float


@pytest.mark.parametrize("case", MONEY_CASES.values(), ids=MONEY_CASES.keys())
def test_a_pandas_frame_keeps_the_float_parse(respx_mock, client, case):
    """pandas has no decimal dtype: a Decimal would make the column `object`
    and stop every vectorized operation on it. Each column keeps the dtype
    the plain parse gives it, so a price with a fraction is `float64`."""
    _respond(respx_mock, case)

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        df = case.call(client, output_format=OutputFormat.DATAFRAME)

    assert isinstance(df, pd.DataFrame)
    assert df[case.column].dtype == "float64"
    assert not any(isinstance(cell, Decimal) for cell in df.to_numpy().ravel())


@pytest.mark.parametrize("case", MONEY_CASES.values(), ids=MONEY_CASES.keys())
def test_a_polars_frame_keeps_the_float_parse(respx_mock, client, case):
    """polars has a Decimal dtype, and the same call returning a different
    dtype depending on which optional library is installed is what #50 rules
    out."""
    _respond(respx_mock, case)

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["polars"]):
        df = case.call(client, output_format=OutputFormat.DATAFRAME)

    assert isinstance(df, pl.DataFrame)
    assert df[case.column].dtype == pl.Float64
    assert not any(isinstance(dtype, pl.Decimal) for dtype in df.schema.values())


# ------------------------------------------------ a model built by hand


def test_a_float_becomes_the_decimal_it_reads_as():
    """What the float is, to its last significant digit: the conversion
    neither rounds a float nor repairs the arithmetic that made it."""
    assert str(to_decimal(65.1)) == "65.1"
    assert to_decimal(65.1) != Decimal(65.1)
    assert str(to_decimal(0.1 + 0.2)) == "0.30000000000000004"


@pytest.mark.parametrize(
    "value",
    [float("nan"), np.float64("nan"), Decimal("NaN"), Decimal("sNaN")],
    ids=["float", "numpy", "Decimal", "signaling"],
)
def test_nan_is_a_missing_amount(value):
    """pandas writes a missing value as NaN; the API writes it as null, which
    the model holds as None. A Decimal NaN would also raise on any ordering
    comparison, so sorting candles by price would fail."""
    assert to_decimal(value) is None


@pytest.mark.parametrize("value", ["NaN", "nan", "-NaN", "sNaN", np.str_("NaN")])
def test_a_string_that_reads_as_nan_is_not_an_amount(value):
    """NaN is a missing amount only as a number, the way pandas writes one. A
    string is read as text the API wrote, and the API writes a missing price
    as null, so this one is refused like any other string that is not an
    amount (#50 review)."""
    with pytest.raises(ValueError) as refusal:
        to_decimal(value)

    assert str(refusal.value) == f"an amount must be finite, not {value!r}"


@pytest.mark.parametrize(
    "value", [float("inf"), -np.float64("inf"), Decimal("Infinity"), "-Infinity"]
)
def test_an_infinity_is_not_an_amount(value):
    with pytest.raises(ValueError, match="must be finite"):
        to_decimal(value)


def test_a_model_applies_the_same_rules_to_a_decimal_it_is_given():
    """A Decimal skips the conversion only when it is already an amount."""

    def price(**money):
        return StockPrice(
            s="ok", symbol="AAPL", changepct=0.0, updated=1765478200, **money
        )

    assert price(mid=Decimal("NaN"), change=Decimal("0.1")).mid is None
    with pytest.raises(ValueError, match=r"StockPrice\.change: an amount must be"):
        price(mid=Decimal("1"), change=Decimal("Infinity"))


def test_a_rational_whose_str_is_not_a_decimal_goes_through_its_float():
    assert to_decimal(Fraction(1, 4)) == Decimal("0.25")
    with pytest.raises(ValueError, match="not a decimal number"):
        to_decimal(Fraction(10**400, 3))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (255, Decimal("255")),
        ("65.10", Decimal("65.10")),
        (Decimal("1.10"), Decimal("1.10")),
        (None, None),
    ],
)
def test_to_decimal_keeps_what_is_already_exact(value, expected):
    result = to_decimal(value)

    assert result == expected
    assert str(result) == str(expected)


@pytest.mark.parametrize(
    ("value", "error"),
    [
        (True, TypeError),
        ("n/a", ValueError),
        ("", ValueError),
        ([1], TypeError),
        (object(), TypeError),
    ],
)
def test_to_decimal_refuses_what_is_not_an_amount(value, error):
    with pytest.raises(error):
        to_decimal(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (np.float64(65.1), "65.1"),
        (np.float32(65.1), "65.1"),
        (np.float32(0.5), "0.5"),
        (np.int64(7), "7"),
    ],
)
def test_a_numpy_scalar_converts_like_the_number_it_is(value, expected):
    """A model built from DataFrame cells gets numpy scalars. Under numpy 2 a
    float64's repr is `np.float64(65.1)`, a float32 is not a float at all,
    and an int64 is not an `int`."""
    assert str(to_decimal(value)) == expected


def test_a_model_built_from_dataframe_cells_holds_decimals():
    """A null price is NaN in a float64 column: it comes back as None, what
    the model holds for the API's null."""
    df = pd.DataFrame({"o": [74.06], "c": [None]}, dtype="float64")

    candle = StockCandle(
        t=1577941200, o=df["o"][0], h=df["o"][0], l=df["o"][0], c=df["c"][0], v=1
    )

    assert candle.o == Decimal("74.06")
    assert type(candle.o) is Decimal
    assert candle.c is None


def test_a_bad_amount_names_the_field_it_was_given_for():
    with pytest.raises(ValueError, match=r"StockPrice\.mid: not a decimal number"):
        StockPrice(
            s="ok",
            symbol="AAPL",
            mid="n/a",
            change=0,
            changepct=0.0,
            updated=1765478200,
        )


@pytest.mark.parametrize(
    "text", ["0.1", "0.2975", "-0.0403", "2.675", "1e-7", "123456789.123456789"]
)
def test_decimal_to_float_is_the_plain_parse(text):
    assert decimal_to_float(Decimal(text)).hex() == float(text).hex()


def test_decimal_to_float_leaves_everything_else_alone():
    marker = object()

    assert decimal_to_float(marker) is marker
    assert type(decimal_to_float(7)) is int


@dataclasses.dataclass
class _Sample:
    price: Decimal
    prices: list[Decimal]
    maybe: Decimal | None
    ratio: float
    ratios: list[float]
    bounds: tuple[float, float]

    def __post_init__(self):
        coerce_numbers(self)


def test_coerce_numbers_follows_the_annotations_of_any_dataclass():
    """Scalars, lists, tuples and optional amounts: the annotation decides,
    not the value, and the container keeps its type."""
    sample = _Sample(
        price=1.5,
        prices=(1, 2.25),
        maybe=None,
        ratio=Decimal("0.5"),
        ratios=[Decimal("0.25"), 1],
        bounds=(Decimal("0.1"), 2),
    )

    assert (sample.price, type(sample.price)) == (Decimal("1.5"), Decimal)
    assert sample.prices == (Decimal("1"), Decimal("2.25"))
    assert all(type(price) is Decimal for price in sample.prices)
    assert sample.maybe is None
    assert decimal_fields(_Sample) == {"price", "prices", "maybe"}
    assert (sample.ratio, type(sample.ratio)) == (0.5, float)
    assert [type(ratio) for ratio in sample.ratios] == [float, int]
    assert sample.bounds == (0.1, 2)
    assert [type(bound) for bound in sample.bounds] == [float, int]


# ------------------------------------------------------------ rendering


def test_a_decimal_renders_as_its_digits():
    quote = StockQuote(
        symbol="AAPL",
        ask=Decimal("278.02"),
        askSize=100,
        bid=Decimal("277.97"),
        bidSize=100,
        mid=Decimal("277.995"),
        last=Decimal("278.0188"),
        change=Decimal("-0.0112"),
        changepct=0.0,
        volume=1,
        updated=1765478200,
    )
    assert "Ask: 278.02\n" in str(quote)
    assert "Decimal" not in str(quote)


@pytest.mark.parametrize("human", [False, True], ids=["api", "human"])
def test_the_earnings_lists_render_as_their_digits(human):
    """The only repr that prints money lists: the list's own repr would show
    `[Decimal('2.67'), None]`."""
    if human:
        earnings = StockEarningsHumanReadable(
            Symbol=["AAPL", "AAPL"],
            Fiscal_Year=[2026, 2026],
            Fiscal_Quarter=[1, 2],
            Date=[1767157200, 1774929600],
            Report_Date=[1769576400, 1777435200],
            Report_Time=["after close", "before open"],
            Currency=["USD", "USD"],
            Reported_EPS=[Decimal("1.88"), None],
            Estimated_EPS=[Decimal("2.67"), None],
            Surprise_EPS=[Decimal("-0.79"), None],
            Surprise_EPS_Percent=[-0.2959, None],
            Updated=[1765861200, 1765861200],
        )
    else:
        earnings = StockEarnings(
            s="ok",
            symbol=["AAPL", "AAPL"],
            fiscalYear=[2026, 2026],
            fiscalQuarter=[1, 2],
            date=[1767157200, 1774929600],
            reportDate=[1769576400, 1777435200],
            reportTime=["after close", "before open"],
            currency=["USD", "USD"],
            reportedEPS=[Decimal("1.88"), None],
            estimatedEPS=[Decimal("2.67"), None],
            surpriseEPS=[Decimal("-0.79"), None],
            surpriseEPSpct=[-0.2959, None],
            updated=[1765861200, 1765861200],
        )

    text = str(earnings)

    assert "Reported EPS: [1.88, None]\n" in text
    assert "Estimated EPS: [2.67, None]\n" in text
    assert "Surprise EPS: [-0.79, None]\n" in text
    assert "Decimal" not in text
