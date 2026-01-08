from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from typing import Annotated, Any

from httpx import Response

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.exceptions import RequestError
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.options import OptionsQuotesInput
from marketdata.internal_settings import MAX_CONCURRENT_REQUESTS, VALID_STATUS_CODES
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.options_quotes import (
    OptionsQuotes,
    OptionsQuotesHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource
from marketdata.sdk_error import MarketDataClientErrorResult, handle_exceptions
from marketdata.utils import merge_csv_texts


@handle_exceptions
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
) -> (
    OptionsQuotes
    | OptionsQuotesHumanReadable
    | dict
    | str
    | MarketDataClientErrorResult
):
    """
    Fetches options quotes for a given symbol.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    def _get_response(symbol: str) -> Response:
        url = self._build_url(
            path=f"options/quotes/{symbol}/",
            user_universal_params=user_universal_params,
            input_params=input_params,
            extra_params=kwargs,
            excluded_params=["symbols"],
        )
        self.logger.debug(f"Using {symbol} with url: {url}")
        response = self.client._make_request(method="GET", url=url)
        return response

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

    if user_universal_params.output_format in [
        OutputFormat.DATAFRAME,
        OutputFormat.INTERNAL,
        OutputFormat.JSON,
    ]:

        def _parse_data(response: Response) -> dict:
            try:
                return response.json()
            except (JSONDecodeError, AttributeError):
                return OptionsQuotes.get_null_dict()

        has_results = any(
            [
                response.status_code in VALID_STATUS_CODES
                for response in responses
                if response is not None
            ]
        )
        if not has_results:
            return MarketDataClientErrorResult(
                error=RequestError("No responses from API")
            )

        data = [_parse_data(response) for response in responses]
        data = output_model.join_dicts(data)

        if user_universal_params.output_format == OutputFormat.DATAFRAME:
            handler = get_dataframe_output_handler()
            return handler(data).get_result(index_columns=["optionSymbol", "Symbol"])

        if user_universal_params.output_format == OutputFormat.INTERNAL:
            return output_model(**data)
        if user_universal_params.output_format == OutputFormat.JSON:
            return data

    if user_universal_params.output_format == OutputFormat.CSV:
        headers = list(output_model.__dataclass_fields__.keys())[1:]
        csv_text = merge_csv_texts([response.text for response in responses], headers)
        return user_universal_params.write_file(csv_text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
