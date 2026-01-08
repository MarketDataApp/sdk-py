from typing import Annotated, Any

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.stocks import StocksNewsInput
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.stocks_news import StockNews, StockNewsHumanReadable
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource
from marketdata.sdk_error import MarketDataClientErrorResult, handle_exceptions
from marketdata.utils import get_data_records


@handle_exceptions
@api_error_handler(service="/v1/stocks/news/")
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=StocksNewsInput)
def news(
    self: BaseResource,
    symbol: Annotated[str, "The symbol to fetch news for"],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: StocksNewsInput,
    **kwargs: dict[str, Any],
) -> (
    list[StockNews]
    | list[StockNewsHumanReadable]
    | dict
    | str
    | MarketDataClientErrorResult
):
    """
    Fetches stock news for a symbol.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    url = self._build_url(
        path=f"stocks/news/{symbol}/",
        user_universal_params=user_universal_params,
        input_params=input_params,
        extra_params=kwargs,
        excluded_params=["symbol"],
    )
    self.logger.debug(f"Fetching stock news for symbol: {symbol} using url: {url}")

    response = self.client._make_request(method="GET", url=url)

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = response.json()
        handler = get_dataframe_output_handler()
        return handler(data).get_result(index_columns=["symbol", "Symbol"])

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        data = get_data_records(response.json(), exclude_keys=["s"])
        output_model = (
            StockNewsHumanReadable
            if user_universal_params.use_human_readable
            else StockNews
        )
        return [output_model(**row) for row in data]

    elif user_universal_params.output_format == OutputFormat.JSON:
        return response.json()

    elif user_universal_params.output_format == OutputFormat.CSV:
        return user_universal_params.write_file(response.text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
