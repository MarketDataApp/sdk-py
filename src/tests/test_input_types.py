import datetime
import importlib
import pkgutil
from pathlib import Path

import pytest
from pydantic import Field, model_validator

import marketdata.input_types as input_types_pkg
from marketdata.exceptions import (
    MinMaxDateValidationError,
    MinMaxValidationError,
    MinMaxValueValidationError,
)
from marketdata.input_types.base import (
    BaseInputType,
    OutputFormat,
    UserUniversalAPIParams,
)
from marketdata.input_types.options import OptionsChainInput
from marketdata.internal_settings import GLOBAL_EXCLUDED_PARAMS


class DummyInput(BaseInputType):
    min_param: datetime.date | str = Field(default="2025-01-01")
    max_param: datetime.date | str = Field(default="2025-01-01")

    @model_validator(mode="after")
    def validate_input(self) -> "DummyInput":
        self._validate_min_max_dates("min_param", "max_param")
        return self


class DummyNumericInput(BaseInputType):
    min_param: float | None = Field(default=None)
    max_param: float | None = Field(default=None)

    @model_validator(mode="after")
    def validate_input(self) -> "DummyNumericInput":
        self._validate_min_max_value("min_param", "max_param")
        return self


def _all_input_models() -> list[type[BaseInputType]]:
    """Return every concrete BaseInputType subclass defined in the SDK.

    Imports each input_types submodule first so all subclasses are registered.
    """
    for module_info in pkgutil.iter_modules(input_types_pkg.__path__):
        importlib.import_module(f"{input_types_pkg.__name__}.{module_info.name}")

    seen: set[type[BaseInputType]] = set()
    stack: list[type[BaseInputType]] = [BaseInputType]
    while stack:
        for sub in stack.pop().__subclasses__():
            if sub not in seen:
                seen.add(sub)
                stack.append(sub)
    # Only audit models shipped in the SDK, not test-only helper subclasses.
    return sorted(
        (c for c in seen if c.__module__.startswith(input_types_pkg.__name__)),
        key=lambda c: c.__name__,
    )


def _snake_case_fields() -> list[tuple[str, str, "object"]]:
    """All (model_name, field_name, field) tuples for fields whose Python name
    differs from a bare API parameter (i.e. contain an underscore)."""
    cases = []
    for model in _all_input_models():
        for field_name, field in model.model_fields.items():
            if "_" in field_name:
                cases.append((model.__name__, field_name, field))
    return cases


_SNAKE_CASE_FIELDS = _snake_case_fields()


def test_snake_case_field_discovery_is_not_empty():
    # Guard: if discovery silently breaks, the parametrized test below would
    # vacuously pass. days_to_expiration alone guarantees at least one case.
    assert _SNAKE_CASE_FIELDS


@pytest.mark.parametrize(
    "model_name, field_name, field",
    _SNAKE_CASE_FIELDS,
    ids=[f"{m}.{f}" for m, f, _ in _SNAKE_CASE_FIELDS],
)
def test_snake_case_input_fields_have_api_alias(model_name, field_name, field):
    """Every multi-word input field must be sent under an explicit API alias.

    The URL builder serializes with ``by_alias=True``; a snake_case field
    without an alias would leak its Python name to the wire (see issue #30,
    ``days_to_expiration`` -> ``dte``). Fields that are never serialized to the
    query string are exempted via GLOBAL_EXCLUDED_PARAMS.
    """
    if field_name in GLOBAL_EXCLUDED_PARAMS:
        return

    assert field.alias and field.alias != field_name, (
        f"{model_name}.{field_name} has no API alias; it would be sent to the "
        f"API as '{field_name}'. Add an alias or exclude it."
    )


def test_base_input_type_min_max_validation():
    with pytest.raises(MinMaxDateValidationError):
        DummyInput(min_param="2025-01-01", max_param="2024-01-01")


def test_base_input_type_min_max_value_validation():
    with pytest.raises(MinMaxValueValidationError):
        DummyNumericInput(min_param=5.0, max_param=1.0)


def test_base_input_type_min_max_value_valid_range():
    instance = DummyNumericInput(min_param=1.0, max_param=5.0)
    assert instance.min_param == 1.0
    assert instance.max_param == 5.0


def test_base_input_type_min_max_value_allows_none():
    # Either bound missing -> no comparison, no error.
    assert DummyNumericInput(min_param=5.0).max_param is None
    assert DummyNumericInput(max_param=1.0).min_param is None
    assert DummyNumericInput().min_param is None


def test_min_max_errors_share_common_base():
    # Both specialized errors must be catchable as the common MinMaxValidationError.
    assert issubclass(MinMaxDateValidationError, MinMaxValidationError)
    assert issubclass(MinMaxValueValidationError, MinMaxValidationError)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_bid": 5.0, "max_bid": 1.0},
        {"min_ask": 10.0, "max_ask": 2.0},
    ],
)
def test_options_chain_input_invalid_price_range(kwargs: dict):
    with pytest.raises(MinMaxValueValidationError):
        OptionsChainInput(symbol="AAPL", **kwargs)


def test_options_chain_input_valid_price_range():
    instance = OptionsChainInput(
        symbol="AAPL", min_bid=1.0, max_bid=5.0, min_ask=2.0, max_ask=10.0
    )
    assert instance.min_bid == 1.0
    assert instance.max_bid == 5.0
    assert instance.min_ask == 2.0
    assert instance.max_ask == 10.0


def test_universal_api_params_api_format():
    params = UserUniversalAPIParams(output_format=OutputFormat.DATAFRAME)
    assert params.api_format == OutputFormat.JSON

    params = UserUniversalAPIParams(output_format=OutputFormat.JSON)
    assert params.api_format == OutputFormat.JSON

    params = UserUniversalAPIParams(output_format=OutputFormat.CSV)
    assert params.api_format == OutputFormat.CSV

    params = UserUniversalAPIParams(output_format=OutputFormat.INTERNAL)
    assert params.api_format == OutputFormat.JSON


def test_universal_api_params_filename(tmp_path: Path):

    params = UserUniversalAPIParams(filename=tmp_path / "test.csv")
    assert params.filename == tmp_path / "test.csv"

    params = UserUniversalAPIParams(filename=str(tmp_path / "test.csv"))
    assert params.filename == tmp_path / "test.csv"

    params = UserUniversalAPIParams(filename=None)
    assert isinstance(params.filename, Path)
    assert params.filename.parent.exists()
    assert params.filename.parent.is_dir()
    assert params.filename.suffix == ".csv"

    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename="test.txt")

    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=tmp_path / "test.txt")

    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=tmp_path / "test")

    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=tmp_path / "test/test.csv")

    existing_file = tmp_path / "test.csv"
    existing_file.touch()
    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=existing_file)

    directory = tmp_path / "test"
    directory.mkdir()
    with pytest.raises(ValueError):
        UserUniversalAPIParams(filename=directory)
