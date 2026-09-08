from typing import Annotated, Any

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.options import OptionsStrikesInput
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.options_strikes import (
    OptionsStrikes,
    OptionsStrikesHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource, no_data_result
from marketdata.utils import encode_path_segment, is_no_data, parse_json


@api_error_handler(service="/v1/options/strikes/")
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=OptionsStrikesInput)
def strikes(
    self: BaseResource,
    symbol: Annotated[str, "The symbol to fetch strikes for"],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: OptionsStrikesInput,
    **kwargs: dict[str, Any],
) -> OptionsStrikes | OptionsStrikesHumanReadable | dict | str:
    """
    Fetches available strikes for a given symbol.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    url = self._build_url(
        path=f"options/strikes/{encode_path_segment(symbol)}/",
        user_universal_params=user_universal_params,
        input_params=input_params,
        extra_params=kwargs,
        excluded_params=["symbol"],
    )
    self.logger.debug("Fetching options strikes...")

    response = self.client._make_request(method="GET", url=url)

    output_model = (
        OptionsStrikesHumanReadable
        if user_universal_params.use_human_readable
        else OptionsStrikes
    )

    if is_no_data(response):
        return no_data_result(
            user_universal_params,
            output_model,
            as_records=False,
            index_columns=[],
            body=parse_json(response),
        )

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = parse_json(response)
        handler = get_dataframe_output_handler()
        return handler(data, output_model, user_universal_params).get_result()

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        data = parse_json(response)
        return output_model(**data)

    elif user_universal_params.output_format == OutputFormat.JSON:
        return parse_json(response)

    elif user_universal_params.output_format == OutputFormat.CSV:
        return user_universal_params.write_file(response.text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
