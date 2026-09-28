from typing import Annotated, Any

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.options import OptionsChainInput
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.columns import _split_fields, _with_extra
from marketdata.output_types.options_chain import (
    OptionsChain,
    OptionsChainHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import (
    BaseResource,
    _check_csv_header,
    _parse_json_object,
    model_errors,
    no_data_result,
)
from marketdata.utils import encode_path_segment, is_no_data


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
) -> OptionsChain | OptionsChainHumanReadable | dict | str:
    """
    Fetches the options chain for a given symbol with extensive filtering options.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    url = self._build_url(
        path=f"options/chain/{encode_path_segment(symbol)}/",
        user_universal_params=user_universal_params,
        input_params=input_params,
        extra_params=kwargs,
        excluded_params=["symbol"],
    )

    self.logger.debug("Fetching options chain...")

    response = self.client._make_request(method="GET", url=url)

    output_model = (
        OptionsChainHumanReadable
        if user_universal_params.use_human_readable
        else OptionsChain
    )

    if is_no_data(response):
        return no_data_result(
            user_universal_params,
            output_model,
            as_records=False,
            index_columns=["optionSymbol", "Symbol"],
            response=response,
        )

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = _parse_json_object(response)
        handler = get_dataframe_output_handler()
        return handler(data, output_model, user_universal_params).get_result(
            index_columns=["optionSymbol", "Symbol"]
        )

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        data = _parse_json_object(response, exact=True)
        fields, extra = _split_fields(output_model, data)
        with model_errors(response):
            return _with_extra(output_model(**fields), extra)

    elif user_universal_params.output_format == OutputFormat.JSON:
        return _parse_json_object(response)

    elif user_universal_params.output_format == OutputFormat.CSV:
        _check_csv_header(
            response,
            output_model,
            with_header=user_universal_params.add_headers is not False,
        )
        return user_universal_params.write_file(response.text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
