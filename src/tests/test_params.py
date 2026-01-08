from pathlib import Path

import pytest

from marketdata.exceptions import KeywordOnlyArgumentError
from marketdata.input_types.base import DateFormat, OutputFormat, UserUniversalAPIParams
from marketdata.input_types.stocks import StocksPricesInput
from marketdata.params import universal_params


def test_universal_params():
    @universal_params(resource_input_type=StocksPricesInput)
    def test_func(
        self,
        *,
        symbols: list[str] | str,
        user_universal_params: UserUniversalAPIParams,
        input_params: StocksPricesInput,
    ):
        return symbols, user_universal_params, input_params

    filename = Path("test.csv")

    assert test_func(
        None,
        symbols="TSLA",
        user_universal_params=UserUniversalAPIParams(
            output_format=OutputFormat.DATAFRAME,
            filename=filename,
            date_format=DateFormat.UNIX,
        ),
        input_params=StocksPricesInput(symbols="TSLA"),
    ) == (
        (
            "TSLA",
            UserUniversalAPIParams(
                output_format=OutputFormat.DATAFRAME,
                filename=filename,
                date_format=DateFormat.UNIX,
            ),
            StocksPricesInput(symbols="TSLA"),
        )
    )


def test_universal_params_bad_method_signature():
    with pytest.raises(ValueError):

        @universal_params
        def test_func(self, symbols: list[str] | str, output_format: OutputFormat):
            return symbols, output_format


def test_universal_params_no_self_positional_argument():
    with pytest.raises(ValueError):

        @universal_params
        def test_func(symbols: list[str] | str, output_format: OutputFormat):
            return symbols, output_format

    with pytest.raises(ValueError):

        @universal_params
        def test_func(
            self,
            symbols: list[str] | str,
            user_universal_params: UserUniversalAPIParams,
        ):
            return symbols, user_universal_params


def test_universal_params_no_user_universal_params_argument():
    with pytest.raises(ValueError):

        @universal_params
        def test_func(self, symbols: list[str] | str):
            return symbols


def test_universal_params_no_input_params_argument():
    with pytest.raises(ValueError):

        @universal_params
        def test_func(self, symbols: list[str] | str, input_params: StocksPricesInput):
            return symbols, input_params


def test_universal_params_keyword_only_argument_error():
    @universal_params(resource_input_type=StocksPricesInput)
    def test_func(
        self,
        symbols: list[str] | str,
        *,
        extra: str | None = None,
        input_params: StocksPricesInput,
        user_universal_params: UserUniversalAPIParams,
    ):
        return symbols, input_params, user_universal_params, extra

    with pytest.raises(KeywordOnlyArgumentError):
        test_func(
            None,
            "TSLA",
            "extra",
            input_params=StocksPricesInput(symbols="TSLA"),
            user_universal_params=UserUniversalAPIParams(
                output_format=OutputFormat.DATAFRAME
            ),
        )
