import datetime
from dataclasses import dataclass
from typing import Union
from unittest.mock import patch

import polars as pl
import pytest
import pytz

from marketdata.input_types.base import DateFormat, UserUniversalAPIParams
from marketdata.output_handlers import _try_get_handler, get_dataframe_output_handler
from marketdata.output_handlers.base import BaseOutputHandler
from marketdata.output_handlers.pandas import PandasOutputHandler
from marketdata.output_handlers.polars import PolarsOutputHandler


@dataclass
class DummySchemaNoDates:
    a: int
    b: int


@dataclass
class DummySchemaUpdated:
    updated: datetime.datetime
    price: float | None = None
    volume: int | None = None


@dataclass
class DummySchemaMultipleDates:
    updated: datetime.datetime
    date: datetime.datetime
    t: datetime.datetime


@dataclass
class DummySchemaOptionalDates:
    dates: list[datetime.date]
    updated: Union[datetime.datetime, None] = None


class PassthroughHandler(BaseOutputHandler):
    def _get_result(self, *args, **kwargs):
        return {"ok": True}


def _make_params(date_format: DateFormat | None = None) -> UserUniversalAPIParams:
    if date_format is None:
        return UserUniversalAPIParams()
    return UserUniversalAPIParams(date_format=date_format)


def test_malformed_output_handler_class():
    class MalformedOutputHandler(BaseOutputHandler):
        pass

    with pytest.raises(TypeError):
        MalformedOutputHandler()


def test_malformed_output_handler_get_result():
    class MalformedOutputHandler(BaseOutputHandler):
        def _get_result(self, *args, **kwargs):
            return super()._get_result(*args, **kwargs)

    with pytest.raises(NotImplementedError):
        MalformedOutputHandler(
            data={},
            output_schema=DummySchemaNoDates,
            user_universal_params=_make_params(),
        ).get_result()


def test_get_dataframe_output_handler_pandas():
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        handler = get_dataframe_output_handler()
        assert handler is not None
        assert handler == PandasOutputHandler


def test_get_dataframe_output_handler_polars():
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["polars"]):
        handler = get_dataframe_output_handler()
        assert handler is not None
        assert handler == PolarsOutputHandler


def test_get_dataframe_output_handler_invalid():
    with (
        patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["invalid"]),
        pytest.raises(ValueError),
    ):
        get_dataframe_output_handler()


def test_try_get_handler():
    handler = _try_get_handler("pandas")
    assert handler is not None

    handler = _try_get_handler("polars")
    assert handler is not None

    handler = _try_get_handler("invalid")
    assert handler is None


def test_base_output_handler_date_columns_from_schema():
    handler = PassthroughHandler(
        data={},
        output_schema=DummySchemaOptionalDates,
        user_universal_params=_make_params(),
    )
    assert handler._get_date_columns() == ["dates"]
    assert handler._get_datetime_columns() == ["updated"]


def test_base_output_handler_non_dataclass_schema():
    handler = PassthroughHandler(
        data={},
        output_schema=dict,
        user_universal_params=_make_params(),
    )
    assert handler._get_date_columns() == []
    assert handler._get_datetime_columns() == []


def test_base_output_handler_validate_result_passthrough():
    handler = PassthroughHandler(
        data={},
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    result = {"ok": True}
    assert handler._validate_result(result) is result


def test_pandas_output_handler_bad_data():
    handler = PandasOutputHandler(
        data=Exception("test"),
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    with pytest.raises(ValueError):
        handler._initialize_dataframe()


def test_polars_output_handler_bad_data():
    handler = PolarsOutputHandler(
        data=Exception("test"),
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    with pytest.raises(ValueError):
        handler._initialize_dataframe()


def test_pandas_output_handler_initialize_dataframe():
    handler = PandasOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler._initialize_dataframe()
    assert df is not None
    assert df.columns.tolist() == ["a", "b"]
    assert df.index.name is None
    assert df.index.is_unique is True
    assert df.index.is_monotonic_increasing is True
    assert df.index.is_monotonic_decreasing is False


def test_pandas_output_handler_validate_dataframe():
    handler = PandasOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
            "s": [7, 8, 9],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler._validate_dataframe(handler._initialize_dataframe())
    assert df is not None
    assert df.columns.tolist() == ["a", "b"]
    assert "s" not in df.columns


def test_pandas_output_handler_get_result():
    handler = PandasOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
            "s": [7, 8, 9],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result(index_columns=["a"])
    assert df is not None
    assert df.columns.tolist() == ["b"]
    assert df.index.name == "a"
    assert df.index.is_unique is True
    assert df.index.is_monotonic_increasing is True
    assert df.index.is_monotonic_decreasing is False


def test_pandas_output_handler_get_result_index_columns():
    handler = PandasOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
            "s": [7, 8, 9],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result(index_columns=["a"])
    assert df is not None
    assert df.columns.tolist() == ["b"]
    assert df.index.name == "a"


def test_polars_output_handler_initialize_dataframe():
    handler = PolarsOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler._initialize_dataframe()
    assert df is not None
    assert df.columns == ["a", "b"]


def test_polars_output_handler_normalize_value():
    handler = PolarsOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    value = handler._normalize_value([1, 2, 3], 3)
    assert value is not None
    assert value.to_list() == [1, 2, 3]

    value = handler._normalize_value(1, 3)
    assert value is not None
    assert value.to_list() == [1, 1, 1]


def test_polars_output_handler_initialize_dataframe():
    handler = PolarsOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler._initialize_dataframe()
    assert df is not None
    assert df.columns == ["a", "b"]


def test_polars_output_handler_get_result():
    handler = PolarsOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
            "s": [7, 8, 9],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result(index_columns=["a"])
    assert df is not None
    assert df.columns == ["a", "b"]
    assert "s" not in df.columns


def test_pandas_output_handler_convert_timestamp_by_name():
    """Test that timestamp columns are converted by column name."""
    # Unix timestamp: 1765552906 = 2026-01-08 19:55:06 EST
    handler = PandasOutputHandler(
        data={
            "symbol": ["AAPL", "MSFT"],
            "updated": [1765552906, 1765552906],
            "price": [278.02, 479.45],
        },
        output_schema=DummySchemaUpdated,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    assert "updated" in df.columns
    # Check that updated is now a datetime type
    assert hasattr(df["updated"].dtype, "tz") or "datetime" in str(df["updated"].dtype)
    # Check that it's timezone-aware
    assert df["updated"].iloc[0].tz is not None
    # Check that price is still numeric
    assert df["price"].dtype in ["float64", "float32", "float"]


def test_pandas_output_handler_non_timestamp_column_not_converted():
    """Test that non-timestamp columns are not converted."""
    handler = PandasOutputHandler(
        data={
            "symbol": ["AAPL"],
            "price": [278.02],
            "volume": [1000],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    # Non-timestamp columns should remain as numeric types
    assert df["price"].dtype in ["float64", "float32", "float"]
    assert df["volume"].dtype in ["int64", "int32", "int"]


def test_pandas_output_handler_timestamp_timezone():
    """Test that converted timestamps are in US/Eastern timezone."""
    # Unix timestamp: 1765552906 = 2026-01-08 19:55:06 EST
    handler = PandasOutputHandler(
        data={
            "updated": [1765552906],
        },
        output_schema=DummySchemaUpdated,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    dt = df["updated"].iloc[0]
    assert dt.tz is not None
    # Check timezone is US/Eastern
    assert str(dt.tz) == "US/Eastern" or "US/Eastern" in str(dt.tz)


def test_pandas_output_handler_multiple_timestamp_columns():
    """Test that multiple timestamp columns are converted."""
    handler = PandasOutputHandler(
        data={
            "updated": [1765552906],
            "date": [1765552906],
            "t": [1765552906],
        },
        output_schema=DummySchemaMultipleDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    for col in ["updated", "date", "t"]:
        assert hasattr(df[col].dtype, "tz") or "datetime" in str(df[col].dtype)


def test_polars_output_handler_convert_timestamp_by_name():
    """Test that timestamp columns are converted by column name."""

    # Unix timestamp: 1765552906 = 2026-01-08 19:55:06 EST
    handler = PolarsOutputHandler(
        data={
            "symbol": ["AAPL", "MSFT"],
            "updated": [1765552906, 1765552906],
            "price": [278.02, 479.45],
        },
        output_schema=DummySchemaUpdated,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    assert "updated" in df.columns
    # Check that updated is now a datetime type
    assert df["updated"].dtype == pl.Datetime("us", "US/Eastern")
    # Check that price is still numeric
    assert df["price"].dtype in [pl.Float64, pl.Float32]


def test_polars_output_handler_non_timestamp_column_not_converted():
    """Test that non-timestamp columns are not converted."""

    handler = PolarsOutputHandler(
        data={
            "symbol": ["AAPL"],
            "price": [278.02],
            "volume": [1000],
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    # Non-timestamp columns should remain as numeric types
    assert df["price"].dtype in [pl.Float64, pl.Float32]
    assert df["volume"].dtype in [pl.Int64, pl.Int32]


def test_polars_output_handler_timestamp_timezone():
    """Test that converted timestamps are in US/Eastern timezone."""

    # Unix timestamp: 1765552906 = 2026-01-08 19:55:06 EST
    handler = PolarsOutputHandler(
        data={
            "updated": [1765552906],
        },
        output_schema=DummySchemaUpdated,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    # Check timezone is US/Eastern
    assert df["updated"].dtype == pl.Datetime("us", "US/Eastern")


def test_polars_output_handler_multiple_timestamp_columns():
    """Test that multiple timestamp columns are converted."""

    handler = PolarsOutputHandler(
        data={
            "updated": [1765552906],
            "date": [1765552906],
            "t": [1765552906],
        },
        output_schema=DummySchemaMultipleDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    for col in ["updated", "date", "t"]:
        assert df[col].dtype == pl.Datetime("us", "US/Eastern")


def test_pandas_output_handler_timestamp_conversion_failure():
    """Test that timestamp conversion failure is handled gracefully."""
    handler = PandasOutputHandler(
        data={
            "updated": ["invalid_timestamp"],  # This will fail conversion
            "price": [278.02],
        },
        output_schema=DummySchemaUpdated,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    # Column should remain as-is when conversion fails
    assert "updated" in df.columns
    # Price should still be numeric
    assert df["price"].dtype in ["float64", "float32", "float"]


def test_polars_output_handler_timestamp_conversion_failure():
    """Test that timestamp conversion failure is handled gracefully."""

    handler = PolarsOutputHandler(
        data={
            "updated": ["invalid_timestamp"],  # This will fail conversion
            "price": [278.02],
        },
        output_schema=DummySchemaUpdated,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    # Column should remain as-is when conversion fails
    assert "updated" in df.columns
    # Price should still be numeric
    assert df["price"].dtype in [pl.Float64, pl.Float32]


def test_pandas_output_handler_normalized_dataframe_fallback():
    """Test that normalized dataframe fallback path is used when plain dataframe fails."""
    handler = PandasOutputHandler(
        data={
            "a": [1],  # Single value, not a list
            "b": [2, 3],  # List with different length
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    assert "a" in df.columns
    assert "b" in df.columns
    assert len(df) == 2


def test_polars_output_handler_normalized_dataframe_fallback():
    """Test that normalized dataframe fallback path is used when plain dataframe fails."""

    handler = PolarsOutputHandler(
        data={
            "a": [1],  # Single value, not a list
            "b": [2, 3],  # List with different length
        },
        output_schema=DummySchemaNoDates,
        user_universal_params=_make_params(),
    )
    df = handler.get_result()
    assert df is not None
    assert "a" in df.columns
    assert "b" in df.columns
    assert len(df) == 2


def test_pandas_output_handler_unix_date_format_no_conversion():
    """Test that timestamps are NOT converted when date_format=DateFormat.UNIX is explicitly set."""
    handler = PandasOutputHandler(
        data={
            "updated": [1765552906],
            "price": [278.02],
        },
        output_schema=DummySchemaUpdated,
        user_universal_params=_make_params(date_format=DateFormat.UNIX),
    )
    df = handler.get_result()
    assert df is not None
    # updated should remain as integer (Unix timestamp)
    assert df["updated"].dtype in ["int64", "int32", "int"]
    assert df["updated"].iloc[0] == 1765552906
    # price should still be numeric
    assert df["price"].dtype in ["float64", "float32", "float"]


def test_polars_output_handler_unix_date_format_no_conversion():
    """Test that timestamps are NOT converted when date_format=DateFormat.UNIX is explicitly set."""
    handler = PolarsOutputHandler(
        data={
            "updated": [1765552906],
            "price": [278.02],
        },
        output_schema=DummySchemaUpdated,
        user_universal_params=_make_params(date_format=DateFormat.UNIX),
    )
    df = handler.get_result()
    assert df is not None
    # updated should remain as integer (Unix timestamp)
    assert df["updated"].dtype in [pl.Int64, pl.Int32]
    assert df["updated"][0] == 1765552906
    # price should still be numeric
    assert df["price"].dtype in [pl.Float64, pl.Float32]
