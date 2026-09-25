"""Every timestamp the SDK renders takes its zone from one constant,
`internal_settings.DEFAULT_TIMEZONE`."""

import ast
import datetime
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest
import pytz

from marketdata import exceptions, internal_settings
from marketdata.exceptions import BaseMarketdataException
from marketdata.input_types.base import UserUniversalAPIParams
from marketdata.output_handlers import pandas as pandas_handler
from marketdata.output_handlers import polars as polars_handler

PACKAGE = Path(internal_settings.__file__).parent
TOKYO = pytz.timezone("Asia/Tokyo")
STAMP = "%Y-%m-%d %H:%M:%S"


@dataclass
class Updated:
    updated: datetime.datetime


@pytest.fixture
def tokyo(monkeypatch):
    """Point every module that renders a timestamp at Asia/Tokyo, a zone with
    no daylight saving time and 13 or 14 hours away from US/Eastern.

    Returns:
        The Asia/Tokyo zone.
    """
    for module in (exceptions, pandas_handler, polars_handler):
        monkeypatch.setattr(module, "DEFAULT_TIMEZONE", TOKYO)
    return TOKYO


def test_the_zone_name_is_written_only_where_the_constant_is_defined():
    """No module of the package builds the zone from a literal of its own."""
    literals = [
        f"{path.relative_to(PACKAGE).as_posix()}:{node.lineno}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and node.value == "US/Eastern"
    ]

    assert len(literals) == 1, literals
    assert literals[0].startswith("internal_settings.py:"), literals


def test_dataframes_and_exception_timestamps_render_in_the_constant_zone(tokyo):
    """A DataFrame from either handler and an exception timestamp all follow
    the zone the constant holds."""
    handler = {
        "data": {"updated": [1765552906]},
        "output_schema": Updated,
        "user_universal_params": UserUniversalAPIParams(),
    }

    pandas_frame = pandas_handler.PandasOutputHandler(**handler).get_result()
    polars_frame = polars_handler.PolarsOutputHandler(**handler).get_result()
    before = datetime.datetime.now(tokyo).strftime(STAMP)
    error = BaseMarketdataException("boom")
    after = datetime.datetime.now(tokyo).strftime(STAMP)

    assert str(pandas_frame["updated"].dt.tz) == "Asia/Tokyo"
    assert polars_frame["updated"].dtype == pl.Datetime("us", "Asia/Tokyo")
    assert before <= error.timestamp <= after
