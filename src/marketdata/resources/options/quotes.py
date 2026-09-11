import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any

from httpx import Response

from marketdata.api_error import api_error_handler, get_resource_retry_adapter
from marketdata.docs import docs
from marketdata.exceptions import MarketdataHttpError
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.options import OptionsQuotesInput
from marketdata.internal_settings import MAX_CONCURRENT_REQUESTS, VALID_STATUS_CODES
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.options_quotes import (
    OptionsQuotes,
    OptionsQuotesHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource, model_columns, no_data_result
from marketdata.utils import (
    encode_path_segment,
    is_no_data,
    json_answer_columns,
    merge_csv_responses,
    parse_json,
)

SERVICE = "/v1/options/quotes/"


@api_error_handler(retry=False)
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

    # Each symbol retries on its own (#83): a failed request is re-issued
    # alone and the healthy responses are kept. The decorator does not retry
    # the whole fan-out (`retry=False`), which would re-send every symbol.
    retry_adapter = get_resource_retry_adapter(self.client, SERVICE)

    def _get_response(symbol: str) -> Response:
        url = self._build_url(
            path=f"options/quotes/{encode_path_segment(symbol)}/",
            user_universal_params=user_universal_params,
            input_params=input_params,
            extra_params=kwargs,
            excluded_params=["symbols"],
        )
        return retry_adapter(self.client._make_request, method="GET", url=url)

    self.logger.debug("Fetching options quotes...")
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        # Each worker runs in a copy of the caller's context so its response
        # lands in the call's metadata scope (#49).
        futures = [
            executor.submit(contextvars.copy_context().run, _get_response, symbol)
            for symbol in input_params.symbols
        ]
        responses = [future.result() for future in futures]

    output_model = (
        OptionsQuotesHumanReadable
        if user_universal_params.use_human_readable
        else OptionsQuotes
    )

    # Per-symbol answers: a symbol with no data (a 404 no_data, or its CSV
    # placeholder, #89) contributes no rows; only when every symbol is empty
    # is the whole call empty.
    usable = [
        response
        for response in responses
        if response.status_code in VALID_STATUS_CODES and not is_no_data(response)
    ]
    if not usable:
        if all(is_no_data(response) for response in responses):
            return no_data_result(
                user_universal_params,
                output_model,
                as_records=False,
                index_columns=["optionSymbol", "Symbol"],
                response=responses[0],
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
        # A body that is not JSON (a proxy's HTML error page) fails the call
        # as it does everywhere else (#82); a fabricated empty row would read
        # as "no options" and break the merge of the healthy symbols.
        data = [parse_json(response) for response in usable]
        # Under `columns=` the API sends the requested keys only, in request
        # order, and every symbol must carry the same ones: a symbol missing
        # one would shift the rows of every symbol after it (the rule
        # `stocks.candles` applies to chunks, #90).
        columns = json_answer_columns(usable, data, output_model.answer_keys())
        data = output_model.join_dicts(data, columns)

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
        # The header comes from the answers (#86): under `columns=` or
        # `use_human_readable` it is not the model's field list, and a body
        # that is not a CSV of this resource fails the call.
        csv_text = merge_csv_responses(
            usable,
            model_columns(output_model),
            with_header=user_universal_params.add_headers is not False,
        )
        return user_universal_params.write_file(csv_text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
