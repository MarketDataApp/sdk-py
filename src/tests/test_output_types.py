"""Invariants of the output models themselves.

`model_columns` translates a `columns=` filter written in API names into the
human-readable columns of the twin model (#87). The translation reads the two
field lists side by side, so the pairing is a contract between models that
lives in no single file; these tests pin it.
"""

import importlib
import inspect
import pkgutil
from dataclasses import dataclass, fields, is_dataclass
from typing import ClassVar, get_origin, get_type_hints

import pytest

import marketdata.output_types as output_types
from marketdata.resources.base import model_columns
from marketdata.utils import column_key


def _human_readable_models() -> list[type]:
    """Every human-readable output model, found by name and not by whether it
    declares a twin: a model that forgot to declare one has to be visible
    here, which is the whole point of the test below."""
    models = []
    for module_info in pkgutil.iter_modules(output_types.__path__):
        module = importlib.import_module(f"{output_types.__name__}.{module_info.name}")
        for value in vars(module).values():
            if (
                is_dataclass(value)
                and value.__module__ == module.__name__
                and value.__name__.endswith("HumanReadable")
            ):
                models.append(value)
    return models


HUMAN_MODELS = _human_readable_models()
PAIRS = [
    (model, model.api_model) for model in HUMAN_MODELS if "api_model" in vars(model)
]


def _columns(model: type) -> list[str]:
    """The columns `model_columns` works with: every field but the status flag."""
    return [field.name for field in fields(model) if field.name != "s"]


@pytest.mark.parametrize("model", HUMAN_MODELS, ids=lambda m: m.__name__)
def test_every_human_readable_model_declares_its_api_twin(model):
    """A human-readable model without an `api_model` silently loses the
    API-name translation: `model_columns` has no positional map for it, so
    `columns=["t"]` selects nothing and the caller gets every column instead.
    Enumerated by class name so a model added without a twin fails here.
    """
    assert "api_model" in vars(model), (
        f"{model.__name__} declares no `api_model` twin, so a `columns=` "
        "filter written in API names would not reach its columns"
    )


@pytest.mark.parametrize("human, api", PAIRS, ids=lambda m: getattr(m, "__name__", m))
def test_every_api_model_twin_lines_up_with_its_model(human, api):
    """What the positional translation actually relies on: the two models
    expose the same number of columns, so `zip` pairs each API name with the
    human-readable column at the same position (`model_columns` zips them
    with `strict=True`, so a mismatch raises there instead of mapping part of
    the columns).

    Note that equal length is the whole contract, not equal order: the pairs
    are written in the same order everywhere except `MarketStatus`
    (`date, status`) and `MarketStatusHumanReadable` (`Status, Date`), which
    stays correct because both API names match a human column by
    `column_key`, so the positional map is never consulted for it.
    """
    assert len(_columns(api)) == len(_columns(human))


@pytest.mark.parametrize("model", HUMAN_MODELS, ids=lambda m: m.__name__)
def test_the_api_twin_is_a_class_variable_not_a_column(model):
    """`api_model` is declared in the class body as a `ClassVar`, so it is
    neither a dataclass field (a column for `model_columns`) nor an argument
    of the constructor."""
    assert get_origin(get_type_hints(model)["api_model"]) is ClassVar
    assert "api_model" not in {field.name for field in fields(model)}
    assert "api_model" not in inspect.signature(model).parameters


def test_model_columns_refuses_a_twin_with_another_column_count():
    """A twin that does not line up is a mistake in this repository, and a
    partial map would select the wrong columns without a word, so the zip is
    strict and the mistake raises."""

    @dataclass
    class Api:
        s: str
        a: int
        b: int

    @dataclass
    class Human:
        api_model: ClassVar[type] = Api
        A: int

    with pytest.raises(ValueError):
        model_columns(Human, ["a"])


@pytest.mark.parametrize("human, api", PAIRS, ids=lambda m: getattr(m, "__name__", m))
def test_every_api_name_selects_a_column_of_its_own(human, api):
    """The translation is a bijection: each API name selects exactly one
    human-readable column, no two land on the same one, and together they
    cover the model. Catches a name that stopped matching anything.
    """
    human_columns = _columns(human)
    selected = [model_columns(human, [api_name]) for api_name in _columns(api)]

    for api_name, columns in zip(_columns(api), selected):
        assert len(columns) == 1, (
            f"{api.__name__}.{api_name} selected {columns} on {human.__name__}; "
            "an API name must select exactly one column"
        )
    flat = [columns[0] for columns in selected]
    assert sorted(flat) == sorted(human_columns), (
        f"{api.__name__} names select {sorted(flat)} on {human.__name__}, "
        f"not its columns {sorted(human_columns)}"
    )


# The API names that no human-readable column matches by `column_key`, so
# `model_columns` resolves them through the positional map. Written out by
# hand, on purpose: deriving the expectation from the position would only
# restate what the code does, and would agree with it even after a pair was
# reordered. Every entry below was read off the API's own field meanings.
POSITIONAL_TRANSLATIONS = {
    "FundsCandlesHumanReadable": {
        "t": "Date",
        "o": "Open",
        "h": "High",
        "l": "Low",
        "c": "Close",
    },
    "OptionsChainHumanReadable": {
        "optionSymbol": "Symbol",
        "expiration": "Expiration_Date",
        "side": "Option_Side",
        "dte": "Days_To_Expiration",
        "updated": "Date",
    },
    "OptionsExpirationsHumanReadable": {"updated": "Date"},
    "OptionsLookupHumanReadable": {"optionSymbol": "Symbol"},
    "OptionsQuotesHumanReadable": {
        "optionSymbol": "Symbol",
        "expiration": "Expiration_Date",
        "side": "Option_Side",
        "dte": "Days_To_Expiration",
        "updated": "Date",
    },
    "OptionsStrikesHumanReadable": {"updated": "Date"},
    "StockCandlesHumanReadable": {
        "t": "Date",
        "o": "Open",
        "h": "High",
        "l": "Low",
        "c": "Close",
        "v": "Volume",
    },
    "StockEarningsHumanReadable": {"surpriseEPSpct": "Surprise_EPS_Percent"},
    "StockNewsHumanReadable": {"updated": "Date"},
    "StockPricesHumanReadable": {
        "change": "Change_Price",
        "changepct": "Change_Percent",
        "updated": "Date",
    },
    "StockQuotesHumanReadable": {
        "change": "Change_Price",
        "changepct": "Change_Percent",
        "updated": "Date",
    },
    # `date` and `status` both match a human column by `column_key`, so this
    # pair never reaches the positional map: see the dedicated test below.
    "MarketStatusHumanReadable": {},
}


@pytest.mark.parametrize("human, api", PAIRS, ids=lambda m: getattr(m, "__name__", m))
def test_the_positional_map_translates_the_names_it_is_supposed_to(human, api):
    """An API name that no human-readable column matches by `column_key`
    (`t`, `optionSymbol`, `surpriseEPSpct`) is resolved by position. Those
    translations are pinned against a hand-written table, so reordering a
    pair, or renaming a column out of its by-name match, has to be a
    deliberate edit here rather than a silent change of meaning.
    """
    human_columns = _columns(human)
    by_key = {column_key(name) for name in human_columns}
    expected = POSITIONAL_TRANSLATIONS[human.__name__]

    positional = [name for name in _columns(api) if column_key(name) not in by_key]
    assert positional == list(expected), (
        f"the API names {human.__name__} resolves by position are "
        f"{positional}, not {list(expected)}; update POSITIONAL_TRANSLATIONS "
        "only after checking what each name really means"
    )
    for api_name, human_name in expected.items():
        assert model_columns(human, [api_name]) == [human_name], (
            f"{api.__name__}.{api_name} must select '{human_name}' on "
            f"{human.__name__}; the two field lists are out of order"
        )


def test_market_status_names_translate_by_name_not_by_position():
    """The one pair written in a different order (`date, status` against
    `Status, Date`). Both API names match a human column through
    `column_key`, so the by-name match decides and the positional map is never
    consulted; renaming either column so it stops matching would swap them.
    """
    from marketdata.output_types.markets_status import (
        MarketStatus,
        MarketStatusHumanReadable,
    )

    assert _columns(MarketStatus) == ["date", "status"]
    assert _columns(MarketStatusHumanReadable) == ["Status", "Date"]
    assert model_columns(MarketStatusHumanReadable, ["date"]) == ["Date"]
    assert model_columns(MarketStatusHumanReadable, ["status"]) == ["Status"]
    assert model_columns(MarketStatusHumanReadable, ["date", "status"]) == [
        "Date",
        "Status",
    ]
    for api_name, human_name in (("date", "Date"), ("status", "Status")):
        assert column_key(api_name) == column_key(human_name)
