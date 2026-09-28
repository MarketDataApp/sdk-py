"""Every timestamp the SDK renders takes its zone from one constant."""

import datetime
import time
from unittest.mock import patch

import pytest
import pytz

from marketdata import exceptions, get_meta, types, utils
from marketdata.exceptions import BadRequestError
from marketdata.input_types.base import OutputFormat
from marketdata.output_handlers import pandas as pandas_handler
from marketdata.output_handlers import polars as polars_handler
from src.tests.conftest import use_real_header_extraction

QUOTES_URL = "https://api.marketdata.app/v1/stocks/quotes/"
UPDATED = 1765552906
TOKYO = pytz.timezone("Asia/Tokyo")
STAMP = "%Y-%m-%d %H:%M:%S"


@pytest.fixture
def tokyo(monkeypatch):
    """Point every module that renders a timestamp at Asia/Tokyo, a zone with
    no daylight saving time and 13 or 14 hours away from US/Eastern.

    Returns:
        The Asia/Tokyo zone.
    """
    for module, name in (
        (utils, "DEFAULT_TIMEZONE"),
        (types, "_DEFAULT_TIMEZONE"),
        (exceptions, "_DEFAULT_TIMEZONE"),
        (pandas_handler, "_DEFAULT_TIMEZONE"),
        (polars_handler, "_DEFAULT_TIMEZONE"),
    ):
        monkeypatch.setattr(module, name, TOKYO)
    return TOKYO


def test_utils_default_timezone_is_us_eastern():
    """`marketdata.utils.DEFAULT_TIMEZONE` is the US/Eastern zone."""
    assert utils.DEFAULT_TIMEZONE is pytz.timezone("US/Eastern")


def test_internal_dates_and_the_credit_reset_follow_the_constant(
    tokyo, load_json, respx_mock, client
):
    """An INTERNAL result's dates and the credit reset read from its headers
    are in the zone the constant holds."""
    use_real_header_extraction(client)
    reset = int(time.time()) + 60
    respx_mock.get(QUOTES_URL).respond(
        json=load_json("stocks_quotes_response_200"),
        headers={
            "x-api-ratelimit-limit": "100",
            "x-api-ratelimit-remaining": "99",
            "x-api-ratelimit-reset": str(reset),
            "x-api-ratelimit-consumed": "1",
        },
        status_code=200,
    )

    quotes = client.stocks.quotes(
        symbols=["AAPL", "MSFT"], output_format=OutputFormat.INTERNAL
    )
    reset_time = get_meta(quotes).rate_limits.reset_time

    assert quotes[0].updated == datetime.datetime.fromtimestamp(UPDATED, tz=tokyo)
    assert str(quotes[0].updated.tzinfo) == "Asia/Tokyo"
    assert reset_time.timestamp() == reset
    assert str(reset_time.tzinfo) == "Asia/Tokyo"


@pytest.mark.parametrize("library", ["pandas", "polars"])
def test_dataframe_dates_follow_the_constant(
    tokyo, load_json, respx_mock, client, library
):
    """A DataFrame's date column is in the zone the constant holds.

    Args:
        library: The DataFrame library the client builds the result with.
    """
    respx_mock.get(QUOTES_URL).respond(
        json=load_json("stocks_quotes_response_200"), status_code=200
    )

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", [library]):
        frame = client.stocks.quotes(
            symbols=["AAPL", "MSFT"], output_format=OutputFormat.DATAFRAME
        )
    updated = frame["updated"].to_list()[0]

    assert updated == datetime.datetime.fromtimestamp(UPDATED, tz=tokyo)
    assert str(updated.tzinfo) == "Asia/Tokyo"


def test_an_error_timestamp_follows_the_constant(tokyo, respx_mock, client):
    """An error the API answered is stamped with the time in the zone the
    constant holds."""
    respx_mock.get(QUOTES_URL).respond(
        json={"errmsg": "Invalid symbol"}, status_code=400
    )

    before = datetime.datetime.now(tokyo).strftime(STAMP)
    with pytest.raises(BadRequestError) as caught:
        client.stocks.quotes(symbols=["AAPL"], output_format=OutputFormat.INTERNAL)
    after = datetime.datetime.now(tokyo).strftime(STAMP)

    assert before <= caught.value.timestamp <= after
