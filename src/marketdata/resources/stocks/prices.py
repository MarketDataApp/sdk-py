from typing import Annotated, Any

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import (
    OutputFormat,
    UserUniversalAPIParams,
)
from marketdata.input_types.stocks import StocksPricesInput
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.stocks_prices import StockPrice, StockPricesHumanReadable
from marketdata.params import universal_params
from marketdata.resources.base import no_data_result
from marketdata.utils import get_data_records, is_no_data, parse_json


@api_error_handler(service="/v1/stocks/prices/")
@docs(exclude_params=["user_universal_params"])
@universal_params(resource_input_type=StocksPricesInput)
def prices(
    self,
    symbols: Annotated[
        list[str] | str, "A single symbol string or a list of symbol strings"
    ],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: StocksPricesInput,
    **kwargs: dict[str, Any],
) -> list[StockPrice] | StockPricesHumanReadable | dict | str:
    """
    Fetches stock prices for one or more symbols.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    url = self._build_url(
        path="stocks/prices/",
        user_universal_params=user_universal_params,
        input_params=input_params,
        extra_params=kwargs,
    )

    self.logger.debug("Fetching stock prices...")
    response = self.client._make_request(method="GET", url=url)

    output_model = (
        StockPricesHumanReadable
        if user_universal_params.use_human_readable
        else StockPrice
    )

    if is_no_data(response):
        return no_data_result(
            user_universal_params,
            output_model,
            as_records=True,
            index_columns=["symbol", "Symbol"],
            body=parse_json(response),
        )

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = parse_json(response)
        handler = get_dataframe_output_handler()
        return handler(data, output_model, user_universal_params).get_result(
            index_columns=["symbol", "Symbol"]
        )

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        data = get_data_records(parse_json(response))
        return [output_model.from_dict(row) for row in data]

    elif user_universal_params.output_format == OutputFormat.JSON:
        return parse_json(response)

    elif user_universal_params.output_format == OutputFormat.CSV:
        return user_universal_params.write_file(response.text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
