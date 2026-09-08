from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from typing import Annotated, Any

from httpx import Response

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.exceptions import MarketdataHttpError, ParseError
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.options import OptionsQuotesInput
from marketdata.internal_settings import MAX_CONCURRENT_REQUESTS, VALID_STATUS_CODES
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.options_quotes import (
    OptionsQuotes,
    OptionsQuotesHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource, no_data_result
from marketdata.utils import (
    encode_path_segment,
    is_no_data,
    merge_csv_texts,
    parse_json,
)


@api_error_handler(service="/v1/options/quotes/")
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=OptionsQuotesInput)
def quotes(
    self: BaseResource,
    symbols: Annotated[
        str | list[str], "A single symbol string or a list of symbol strings"
    ],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: OptionsQuotesInput,
    **kwargs: dict[str, Any],
) -> OptionsQuotes | OptionsQuotesHumanReadable | dict | str:
    """
    Fetches options quotes for a given symbol.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    def _get_response(symbol: str) -> Response:
        url = self._build_url(
            path=f"options/quotes/{encode_path_segment(symbol)}/",
            user_universal_params=user_universal_params,
            input_params=input_params,
            extra_params=kwargs,
            excluded_params=["symbols"],
        )
        response = self.client._make_request(method="GET", url=url)
        return response

    self.logger.debug("Fetching options quotes...")
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        futures = [
            executor.submit(_get_response, symbol) for symbol in input_params.symbols
        ]
        responses = [future.result() for future in futures]

    output_model = (
        OptionsQuotesHumanReadable
        if user_universal_params.use_human_readable
        else OptionsQuotes
    )

    # Per-symbol answers: a symbol with no data (404 no_data) contributes no
    # rows; only when every symbol is empty is the whole call empty.
    usable = [
        response for response in responses if response.status_code in VALID_STATUS_CODES
    ]
    if not usable:
        if all(is_no_data(response) for response in responses):
            return no_data_result(
                user_universal_params,
                output_model,
                as_records=False,
                index_columns=["optionSymbol", "Symbol"],
                body=parse_json(responses[0]),
            )
        # The API answered, just not with anything usable. Terminal on purpose:
        # raising a retryable class here would re-run the whole fan-out.
        raise MarketdataHttpError(
            message="No responses from API",
            request=responses[0].request,
            response=responses[0],
        )

    if user_universal_params.output_format in [
        OutputFormat.DATAFRAME,
        OutputFormat.INTERNAL,
        OutputFormat.JSON,
    ]:

        def _parse_data(response: Response) -> dict:
            try:
                return parse_json(response)
            except ParseError:
                return OptionsQuotes.get_null_dict()

        data = [_parse_data(response) for response in usable]
        data = output_model.join_dicts(data)

        if user_universal_params.output_format == OutputFormat.DATAFRAME:
            handler = get_dataframe_output_handler()
            return handler(data, output_model, user_universal_params).get_result(
                index_columns=["optionSymbol", "Symbol"]
            )

        if user_universal_params.output_format == OutputFormat.INTERNAL:
            return output_model(**data)
        if user_universal_params.output_format == OutputFormat.JSON:
            return data

    if user_universal_params.output_format == OutputFormat.CSV:
        headers = list(output_model.__dataclass_fields__.keys())[1:]
        csv_text = merge_csv_texts([response.text for response in usable], headers)
        return user_universal_params.write_file(csv_text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
