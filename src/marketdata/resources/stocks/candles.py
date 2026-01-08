import datetime
import itertools
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from typing import Annotated, Any

import httpx

from marketdata.api_error import api_error_handler
from marketdata.docs import docs
from marketdata.input_types.base import OutputFormat, UserUniversalAPIParams
from marketdata.input_types.stocks import StocksCandlesInput
from marketdata.internal_settings import HTTP_TIMEOUT, MAX_CONCURRENT_REQUESTS
from marketdata.output_handlers import get_dataframe_output_handler
from marketdata.output_types.stocks_candles import (
    StockCandle,
    StockCandlesHumanReadable,
)
from marketdata.params import universal_params
from marketdata.resources.base import BaseResource
from marketdata.sdk_error import MarketDataClientErrorResult, handle_exceptions
from marketdata.utils import (
    get_data_records,
    merge_csv_texts,
    split_dates_by_timeframe,
)


@handle_exceptions
@api_error_handler(service="/v1/stocks/candles/")
@docs(exclude_params=["user_universal_params", "input_params"])
@universal_params(resource_input_type=StocksCandlesInput)
def candles(
    self: BaseResource,
    symbol: Annotated[str, "The symbol to fetch candles for"],
    *,
    user_universal_params: UserUniversalAPIParams,
    input_params: StocksCandlesInput,
    **kwargs: dict[str, Any],
) -> (
    list[StockCandle]
    | StockCandlesHumanReadable
    | dict
    | str
    | MarketDataClientErrorResult
):
    """
    Fetches stock candles data for a symbol.

    Supports various timeframes (minutely, hourly, daily, weekly, monthly, yearly)
    and automatically handles large date ranges by splitting them into year-long
    chunks and fetching them concurrently.
    """
    user_universal_params = self._validate_user_universal_params(
        self.client.default_params, user_universal_params
    )

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
            path=f"stocks/candles/{input_params.resolution}/{symbol}/",
            user_universal_params=user_universal_params,
            input_params=input_params,
            extra_params=kwargs,
            excluded_params=["symbol", "resolution"],
        )
        self.logger.debug(
            f"Fetching stock candles for symbol: {symbol} using url: {url}"
        )
        return self.client._make_request(method="GET", url=url)

    if input_params.from_date is not None:
        if input_params.is_intraday:
            year_ranges = split_dates_by_timeframe(
                input_params.from_date,
                input_params.to_date or datetime.date.today(),
                datetime.timedelta(days=365),
            )
        else:
            year_ranges = [(input_params.from_date, input_params.to_date)]
    else:
        year_ranges = [(None, None)]

    responses = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        futures = [
            executor.submit(_get_response, input_params, from_date, to_date)
            for from_date, to_date in year_ranges
        ]
        responses = [future.result(timeout=HTTP_TIMEOUT) for future in futures]

    output_model = (
        StockCandlesHumanReadable
        if user_universal_params.use_human_readable
        else StockCandle
    )

    def _get_responses_data(responses: list[httpx.Response]) -> list[dict]:
        responses_data = [response.json() for response in responses]
        result = {}
        for field in fields(output_model):
            result[field.name] = list(
                itertools.chain.from_iterable(
                    [responses_data[i][field.name] for i in range(len(responses_data))]
                )
            )
        return result

    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        data = _get_responses_data(responses)
        handler = get_dataframe_output_handler()
        return handler(data).get_result(index_columns=["t", "Date"])

    elif user_universal_params.output_format == OutputFormat.INTERNAL:
        data = _get_responses_data(responses)
        data = get_data_records(data, exclude_keys=["s"])
        return [output_model(**row) for row in data]

    elif user_universal_params.output_format == OutputFormat.JSON:
        data = _get_responses_data(responses)
        return data

    elif user_universal_params.output_format == OutputFormat.CSV:
        field_names = [field.name for field in fields(output_model)]
        data = merge_csv_texts([response.text for response in responses], field_names)
        return user_universal_params.write_file(data)

    # This line should never be reached due to the universal_params decorator validating the output format
    # but we add it to satisfy the type checker and avoid coverage errors.
    raise ValueError(
        f"Invalid output format: {user_universal_params.output_format}"
    )  # pragma: no cover
