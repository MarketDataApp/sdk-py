from typing import Annotated, Any
from urllib.parse import quote

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.options import OptionsLookupInput
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.options_lookup import (
    OptionsLookup,
    OptionsLookupHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource
from marketdata.sdk_error import MarketDataClientErrorResult, handle_exceptions


@handle_exceptions
@api_error_handler(service="/v1/options/lookup/")
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=OptionsLookupInput)
def lookup(
    self: BaseResource,
    lookup: Annotated[str, "The lookup string to lookup options for"],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: OptionsLookupInput,
    **kwargs: dict[str, Any],
) -> (
    OptionsLookup
    | OptionsLookupHumanReadable
    | dict
    | str
    | MarketDataClientErrorResult
):
    """
    Fetches options lookup data for a given lookup string.
    The lookup string should contain the underlying symbol, expiration date, strike price, and option side.
    """
    self.logger.debug(f"Fetching options lookup for lookup: {lookup}")
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    # All params are already in the path
    _format_date = lambda date: date.strftime("%d-%M-%Y")
    excluded_params = OptionsLookupInput.model_fields.keys()
    lookup_quote = quote(input_params.lookup)

    url = self._build_url(
        path=f"options/lookup/{lookup_quote}/",
        user_universal_params=user_universal_params,
        input_params=input_params,
        extra_params=kwargs,
        excluded_params=excluded_params,
    )
    self.logger.debug(f"Using {lookup} with url: {url}")

    response = self.client._make_request(method="GET", url=url)

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = response.json()
        handler = get_dataframe_output_handler()
        return handler(data).get_result(index_columns=["optionSymbol", "Symbol"])

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        output_model = (
            OptionsLookupHumanReadable
            if user_universal_params.use_human_readable
            else OptionsLookup
        )
        data = response.json()
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
