"""Money is a ``Decimal`` in the INTERNAL models, and only there (#50).

The INTERNAL path of a resource with money fields decodes the body with
``parse_float=Decimal``, and every model then puts each number back where its
annotation says: Decimals in the money fields, the plain parse's floats
everywhere else. The DataFrame and JSON outputs keep the plain float parse.
"""

import dataclasses
import datetime
import importlib
import inspect
import json
import math
import pathlib
import pkgutil
import typing
from decimal import Decimal
from unittest.mock import patch

import numpy as np
import pandas as pd
import polars as pl
import pytest

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
from marketdata.output_types.options_strikes import (
    OptionsStrikes,
    OptionsStrikesHumanReadable,
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

DATA_DIR = pathlib.Path(__file__).parent / "data"
API = "https://api.marketdata.app"
OPTION = "AAPL271217C00255000"

# More digits than a double holds: a float parse reads it as 65.1, so only a
# parse that never goes through a float can hand it to the model intact.
EXACT = "65.10000000000000000001"

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
    StockQuote: {"ask", "bid", "mid", "last", "change"},
    StockQuotesHumanReadable: {"Ask", "Bid", "Mid", "Last", "Change_Price"},
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

STRIKES_MODELS = (OptionsStrikes, OptionsStrikesHumanReadable)


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
    "options.strikes": Case(
        "options_strikes_response_200",
        f"{API}/v1/options/strikes/AAPL/",
        lambda c, **kw: c.options.strikes("AAPL", **kw),
        "2025-12-12",
        lambda r: getattr(r, "2025-12-12")[0],
    ),
    "options.strikes human": Case(
        "options_strikes_human_response_200",
        f"{API}/v1/options/strikes/AAPL/",
        lambda c, **kw: c.options.strikes("AAPL", use_human_readable=True, **kw),
        "2025-12-12",
        lambda r: getattr(r, "2025-12-12")[0],
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
    "options.strikes": ("updated",),
    "options.strikes human": ("Date",),
}
# 46003.5 days after 1899-12-30.
SPREADSHEET_DATE = "46003.5"
SPREADSHEET_DATETIME = datetime.datetime(2025, 12, 12, 12, 0)

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
}


def _load_fixture(name: str) -> dict:
    path = DATA_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _respond(respx_mock, case: Case, body: bytes | None = None) -> None:
    if body is None:
        body = json.dumps(_load_fixture(case.fixture)).encode()
    respx_mock.get(case.url).respond(
        content=body, headers={"content-type": "application/json"}
    )


def _holds_decimal(value) -> bool:
    if isinstance(value, Decimal):
        return True
    if isinstance(value, dict):
        return any(_holds_decimal(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_holds_decimal(item) for item in value)
    return False


def _money_holds_decimals_and_nothing_else(result) -> int:
    """Walk an INTERNAL result: every money value is a Decimal, and no other
    field holds one. Returns how many money values it checked."""
    checked = 0
    for model in result if isinstance(result, list) else [result]:
        fixed = {field.name for field in dataclasses.fields(model)}
        money = decimal_fields(type(model))
        for name, value in vars(model).items():
            is_strike_column = isinstance(model, STRIKES_MODELS) and name not in fixed
            if name in money or is_strike_column:
                values = value if isinstance(value, list) else [value]
                present = [item for item in values if item is not None]
                assert all(isinstance(item, Decimal) for item in present), name
                checked += len(present)
            else:
                assert not _holds_decimal(value), name
    return checked


def _mentions(annotation, target: type) -> bool:
    return annotation is target or any(
        _mentions(arg, target) for arg in typing.get_args(annotation)
    )


def _dates_in(result) -> list:
    """Every value of every datetime-annotated field of an INTERNAL result."""
    dates = []
    for model in result if isinstance(result, list) else [result]:
        hints = typing.get_type_hints(type(model))
        for field in dataclasses.fields(model):
            if _mentions(hints[field.name], datetime.datetime):
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


def test_a_number_past_what_a_decimal_holds_is_a_parse_error(respx_mock, client):
    """The float parse reads an exponent this size as `inf`; a Decimal cannot
    hold it and raises `decimal.InvalidOperation`, which is not an SDK
    exception. The INTERNAL call fails like any other body it cannot read,
    and the JSON output of the same body is what it always was."""
    respx_mock.get(f"{API}/v1/stocks/prices/").respond(
        content=(
            b'{"s": "ok", "symbol": ["AAPL"], "mid": [1e9999999999999999999], '
            b'"change": [0.1], "changepct": [0.01], "updated": [1765478200]}'
        ),
        headers={"content-type": "application/json"},
    )

    with pytest.raises(ParseError, match="out of range"):
        client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)
    body = client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    assert body["mid"] == [math.inf]


# ------------------------------ dates the exact parse would have broken


def test_every_money_case_lists_its_dates():
    assert DATE_KEYS.keys() == MONEY_CASES.keys()


@pytest.mark.parametrize("name", MONEY_CASES)
def test_a_spreadsheet_date_still_reads(respx_mock, client, name):
    """Under `dateformat=spreadsheet` a date is a number with a fraction, so
    the exact parse makes it a Decimal, which `format_timestamp` does not
    read. The model gives it back its float before formatting it, and
    `OptionsStrikes`, which builds itself in its own `__init__`, does the same
    by hand."""
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
    assert str(to_decimal(65.1)) == "65.1"
    assert to_decimal(65.1) != Decimal(65.1)


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
        (np.float32(0.5), "0.5"),
        (np.int64(7), "7"),
    ],
)
def test_a_numpy_scalar_converts_like_the_number_it_is(value, expected):
    """A model built from DataFrame cells gets numpy scalars. Under numpy 2 a
    float64's repr is `np.float64(65.1)`, and an int64 is not an `int`."""
    assert str(to_decimal(value)) == expected


def test_a_model_built_from_dataframe_cells_holds_decimals():
    df = pd.DataFrame({"o": [74.06]})

    candle = StockCandle(
        t=1577941200, o=df["o"][0], h=df["o"][0], l=df["o"][0], c=df["o"][0], v=1
    )

    assert candle.o == Decimal("74.06")
    assert type(candle.o) is Decimal


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
    earnings = StockEarnings(
        s="ok",
        symbol=["AAPL"],
        fiscalYear=[2026],
        fiscalQuarter=[1],
        date=[1767157200],
        reportDate=[1769576400],
        reportTime=["after close"],
        currency=["USD"],
        reportedEPS=[None],
        estimatedEPS=[Decimal("2.67")],
        surpriseEPS=[None],
        surpriseEPSpct=[None],
        updated=[1765861200],
    )

    assert "Ask: 278.02\n" in str(quote)
    assert "Estimated EPS: [2.67]\n" in str(earnings)
    assert "Reported EPS: [None]\n" in str(earnings)
    assert "Decimal" not in str(quote) + str(earnings)
