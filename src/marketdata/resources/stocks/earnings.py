from typing import Annotated, Any

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.stocks import StocksEarningsInput
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.stocks_earnings import (
    StockEarnings,
    StockEarningsHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource
from marketdata.sdk_error import MarketDataClientErrorResult, handle_exceptions


@handle_exceptions
@api_error_handler(service="/v1/stocks/earnings/")
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=StocksEarningsInput)
def earnings(
    self: BaseResource,
    symbol: Annotated[str, "The symbol to fetch earnings for"],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: StocksEarningsInput,
    **kwargs: dict[str, Any],
) -> (
    StockEarnings
    | StockEarningsHumanReadable
    | dict
    | str
    | MarketDataClientErrorResult
):
    """
    Fetches stock earnings data for a symbol.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    url = self._build_url(
        path=f"stocks/earnings/{symbol}/",
        user_universal_params=user_universal_params,
        input_params=input_params,
        extra_params=kwargs,
        excluded_params=["symbol"],
    )

    self.logger.debug(f"Fetching stock earnings for symbol: {symbol} using url: {url}")

    response = self.client._make_request(method="GET", url=url)

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = response.json()
        handler = get_dataframe_output_handler()
        return handler(data).get_result(index_columns=["symbol", "Symbol"])

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        output_model = (
            StockEarningsHumanReadable
            if user_universal_params.use_human_readable
            else StockEarnings
        )
        data = response.json()
        return output_model.from_dict(data)

    elif user_universal_params.output_format == OutputFormat.JSON:
        return response.json()

    elif user_universal_params.output_format == OutputFormat.CSV:
        return user_universal_params.write_file(response.text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
