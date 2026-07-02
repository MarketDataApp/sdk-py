from typing import Annotated, Any

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.options import OptionsExpirationsInput
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.options_expirations import (
    OptionsExpirations,
    OptionsExpirationsHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource
from marketdata.sdk_error import MarketDataClientErrorResult, handle_exceptions
from marketdata.utils import encode_path_segment


@handle_exceptions
@api_error_handler(service="/v1/options/expirations/")
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=OptionsExpirationsInput)
def expirations(
    self: BaseResource,
    symbol: Annotated[str, "The stock symbol to fetch expirations for"],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: OptionsExpirationsInput,
    **kwargs: dict[str, Any],
) -> (
    OptionsExpirations
    | OptionsExpirationsHumanReadable
    | dict
    | str
    | MarketDataClientErrorResult
):
    """
    Fetches available expiration dates for a given symbol.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    # Force dateformat=unix so the API returns unix timestamps instead of
    # date-only strings (yyyy-mm-dd) which caused off-by-one-day errors
    # when converted to datetime objects with timezone info.
    user_universal_params.date_format = None

    url = self._build_url(
        path=f"options/expirations/{encode_path_segment(symbol)}/",
        user_universal_params=user_universal_params,
        input_params=input_params,
        extra_params=kwargs,
        excluded_params=["symbol"],
    )
    url += "&dateformat=unix"
    self.logger.debug("Fetching options expirations...")

    response = self.client._make_request(method="GET", url=url)

    output_model = (
        OptionsExpirationsHumanReadable
        if user_universal_params.use_human_readable
        else OptionsExpirations
    )

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = response.json()
        handler = get_dataframe_output_handler()
        # When the user explicitly filters columns we must not force
        # "expirations" into the index: doing so when it is the only requested
        # column would promote all data into the index and leave an apparently
        # empty DataFrame.
        index_columns = [] if user_universal_params.columns else ["expirations"]
        return handler(data, output_model, user_universal_params).get_result(
            index_columns=index_columns
        )

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
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
