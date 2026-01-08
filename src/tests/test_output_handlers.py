from unittest.mock import patch

import pytest

from marketdata.output_handlers import _try_get_handler, get_dataframe_output_handler
from marketdata.output_handlers.base import BaseOutputHandler
from marketdata.output_handlers.pandas import PandasOutputHandler
from marketdata.output_handlers.polars import PolarsOutputHandler


def test_malformed_output_handler_class():
    class MalformedOutputHandler(BaseOutputHandler):
        pass

    with pytest.raises(TypeError):
        MalformedOutputHandler()


def test_malformed_output_handler_get_result():
    class MalformedOutputHandler(BaseOutputHandler):
        def get_result(self, *args, **kwargs):
            return super().get_result(*args, **kwargs)

    with pytest.raises(NotImplementedError):
        MalformedOutputHandler(data={}).get_result()


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


def test_pandas_output_handler_bad_data():
    handler = PandasOutputHandler(data=Exception("test"))
    with pytest.raises(ValueError):
        handler._initialize_dataframe()


def test_polars_output_handler_bad_data():
    handler = PolarsOutputHandler(data=Exception("test"))
    with pytest.raises(ValueError):
        handler._initialize_dataframe()


def test_pandas_output_handler_initialize_dataframe():
    handler = PandasOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        }
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
        }
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
        }
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
        }
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
        }
    )
    df = handler._initialize_dataframe()
    assert df is not None
    assert df.columns == ["a", "b"]


def test_polars_output_handler_normalize_value():
    handler = PolarsOutputHandler(
        data={
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        }
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
        }
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
        }
    )
    df = handler.get_result(index_columns=["a"])
    assert df is not None
    assert df.columns == ["a", "b"]
    assert "s" not in df.columns
