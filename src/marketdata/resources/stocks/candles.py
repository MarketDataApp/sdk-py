import contextvars
import datetime
import itertools
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any

import httpx

from marketdata.api_error import api_error_handler, get_resource_retry_adapter
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.stocks import StocksCandlesInput
from marketdata.internal_settings import MAX_CONCURRENT_REQUESTS
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.stocks_candles import (
    StockCandle,
    StockCandlesHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource, model_columns, no_data_result
from marketdata.utils import (
    encode_path_segment,
    get_data_records,
    is_no_data,
    json_answer_columns,
    merge_csv_responses,
    parse_json,
    split_dates_by_timeframe,
)

SERVICE = "/v1/stocks/candles/"


@api_error_handler(retry=False)
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=StocksCandlesInput)
def candles(
    self: BaseResource,
    symbol: Annotated[str, "The symbol to fetch candles for"],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: StocksCandlesInput,
    **kwargs: dict[str, Any],
) -> list[StockCandle] | StockCandlesHumanReadable | dict | str:
    """
    Fetches stock candles data for a symbol.

    Supports various timeframes (minutely, hourly, daily, weekly, monthly, yearly)
    and automatically handles large date ranges by splitting them into year-long,
    non-overlapping chunks and fetching them concurrently.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

    # Each chunk retries on its own (#83): a failed request is re-issued
    # alone and the healthy responses are kept. The decorator does not retry
    # the whole fan-out (`retry=False`), which would re-send every chunk.
    retry_adapter = get_resource_retry_adapter(self.client, SERVICE)

    def _get_response(
        input_params: StocksCandlesInput,
        from_date: datetime.datetime,
        to_date: datetime.datetime,
    ) -> httpx.Response:
        input_params = input_params.model_copy()

        if from_date is not None:
            input_params.from_date = from_date
        if to_date is not None:
            input_params.to_date = to_date

        url = self._build_url(
            path=f"stocks/candles/{encode_path_segment(input_params.resolution)}/{encode_path_segment(symbol)}/",
            user_universal_params=user_universal_params,
            input_params=input_params,
            extra_params=kwargs,
            excluded_params=["symbol", "resolution"],
        )
        return retry_adapter(self.client._make_request, method="GET", url=url)

    if input_params.from_date is not None:
        if input_params.is_intraday:
            year_ranges = split_dates_by_timeframe(
                input_params.from_date,
                input_params.to_date or datetime.datetime.now(),
                datetime.timedelta(days=365),
            )
        else:
            year_ranges = [(input_params.from_date, input_params.to_date)]
    else:
        year_ranges = [(None, None)]

    self.logger.debug("Fetching stock candles...")
    responses = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        # Each worker runs in a copy of the caller's context so its response
        # lands in the call's metadata scope (#49).
        futures = [
            executor.submit(
                contextvars.copy_context().run,
                _get_response,
                input_params,
                from_date,
                to_date,
            )
            for from_date, to_date in year_ranges
        ]
        # No deadline on the future: each request is bounded by the HTTP
        # timeout and its own retries, a chunk on its second attempt outlives
        # one timeout, and the executor's exit joins every worker anyway, so a
        # future timeout could only ever surface after they had all finished.
        responses = [future.result() for future in futures]
    # A chunk with no data (a 404 no_data, or its CSV placeholder, #89) is
    # simply absent from the merge.
    responses = [response for response in responses if not is_no_data(response)]

    output_model = (
        StockCandlesHumanReadable
        if user_universal_params.use_human_readable
        else StockCandle
    )

    if not responses:
        return no_data_result(
            user_universal_params,
            output_model,
            as_records=True,
            index_columns=["t", "Date"],
        )

    def _get_responses_data(responses: list[httpx.Response]) -> dict:
        responses_data = [parse_json(response) for response in responses]
        # Under `columns=` the API sends the requested keys only (#90), so the
        # merge covers the model fields the first chunk carries, in model
        # order, and every chunk must carry them.
        present = json_answer_columns(
            responses, responses_data, model_columns(output_model)
        )
        return {
            name: list(
                itertools.chain.from_iterable(data[name] for data in responses_data)
            )
            for name in present
        }

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = _get_responses_data(responses)
        handler = get_dataframe_output_handler()
        return handler(data, output_model, user_universal_params).get_result(
            index_columns=["t", "Date"]
        )

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        data = _get_responses_data(responses)
        data = get_data_records(data, exclude_keys=["s"])
        return [output_model(**row) for row in data]

    elif user_universal_params.output_format == OutputFormat.JSON:
        data = _get_responses_data(responses)
        return data

    elif user_universal_params.output_format == OutputFormat.CSV:
        # The header comes from the answers (#86): under `columns=` or
        # `use_human_readable` it is not the model's field list, and a body
        # that is not a CSV of this resource fails the call.
        csv_text = merge_csv_responses(
            responses,
            model_columns(output_model),
            with_header=user_universal_params.add_headers is not False,
        )
        return user_universal_params.write_file(csv_text)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
