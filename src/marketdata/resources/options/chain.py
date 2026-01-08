from typing import Annotated, Any

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.options import OptionsChainInput
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.options_chain import (
    OptionsChain,
    OptionsChainHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource
from marketdata.sdk_error import MarketDataClientErrorResult, handle_exceptions


@handle_exceptions
@api_error_handler(service="/v1/options/chain/")
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=OptionsChainInput)
def chain(
    self: BaseResource,
    symbol: Annotated[str, "The stock symbol to fetch options chain for"],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: OptionsChainInput,
    **kwargs: dict[str, Any],
) -> (
    OptionsChain | OptionsChainHumanReadable | dict | str | MarketDataClientErrorResult
):
    """
    Fetches the options chain for a given symbol with extensive filtering options.
    """
    self.logger.debug(f"Fetching options chain for symbol: {symbol}")
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    url = self._build_url(
        path=f"options/chain/{symbol}/",
        user_universal_params=user_universal_params,
        input_params=input_params,
        extra_params=kwargs,
        excluded_params=["symbol"],
    )

    self.logger.debug(f"Using {symbol} with url: {url}")

    response = self.client._make_request(method="GET", url=url)

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = response.json()
        handler = get_dataframe_output_handler()
        return handler(data).get_result(index_columns=["optionSymbol", "Symbol"])

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        output_model = (
            OptionsChainHumanReadable
            if user_universal_params.use_human_readable
            else OptionsChain
        )
        data = response.json()
        if user_universal_params.use_human_readable:
            data = {k.replace(" ", "_"): v for k, v in data.items()}
        return output_model(**data)

    elif user_universal_params.output_format == OutputFormat.JSON:
        return response.json()

    elif user_universal_params.output_format == OutputFormat.CSV:
        return user_universal_params.write_file(response.text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
