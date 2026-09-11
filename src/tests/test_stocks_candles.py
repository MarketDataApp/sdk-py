import copy
import datetime
import pathlib
from unittest.mock import patch

import httpx
import pytest
import pytz
from freezegun import freeze_time

from marketdata.exceptions import ParseError, ServerError
from marketdata.input_types.base import DateFormat, OutputFormat
from marketdata.input_types.stocks import StocksCandlesInput
from marketdata.output_types.stocks_candles import (
    StockCandle,
    StockCandlesHumanReadable,
)


def test_stock_candle_str():
    instance = StockCandle(
        t=1577941200,
        o=[280.02],
        h=[280.02],
        l=[280.02],
        c=[280.02],
        v=[100],
    )
    assert isinstance(str(instance), str)


def test_stocks_candles_human_readable_str():
    timestamp = int(
        datetime.datetime(
            2025, 1, 1, 0, 0, 0, 0, pytz.timezone("US/Eastern")
        ).timestamp()
    )
    data = {
        "Date": timestamp,
        "Open": 280.02,
        "High": 280.02,
        "Low": 280.02,
        "Close": 280.02,
        "Volume": 100,
    }
    instance = StockCandlesHumanReadable(**data)
    assert isinstance(str(instance), str)


def test_stocks_candles_input_resolution_validation():

    valid_inputs = [
        "minutely",
        "1",
        "15M",
        "hourly",
        "H",
        "1H",
        "daily",
        "D",
        "1D",
        "weekly",
        "W",
        "1W",
        "monthly",
        "M",
        "1M",
        "yearly",
        "Y",
        "1Y",
        "1y",
        "1m",
    ]

    invalid_inputs = [
        "M1",
        "Random",
        "1x5",
        "15x",
        "15x5",
        "15x5M",
        "15x5H",
        "15x5D",
        "15x5W",
        "15x5M",
        "15x5y",
    ]

    for _input in valid_inputs:
        assert StocksCandlesInput(symbol="AAPL", resolution=_input).resolution == _input

    for _input in invalid_inputs:
        with pytest.raises(ValueError):
            StocksCandlesInput(symbol="AAPL", resolution=_input)


def test_get_stocks_candles_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
    )
    assert len(candles) == 253
    assert candles[0].t == datetime.datetime.fromtimestamp(
        1577941200, tz=pytz.timezone("US/Eastern")
    )
    assert candles[0].o == 74.06
    assert candles[0].h == 75.15
    assert candles[0].l == 73.7975
    assert candles[0].c == 75.0875
    assert candles[0].v == 135647456


def test_get_stocks_candles_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    candles = client.stocks.candles(
        symbol="AAPL", resolution="D", output_format=OutputFormat.JSON
    )
    mock_data.pop("s")
    assert candles == mock_data


def test_get_stocks_candles_response_200_internal_human_readable(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        output_format=OutputFormat.INTERNAL,
        use_human_readable=True,
    )
    assert len(candles) == 253
    assert candles[0].Date == datetime.datetime.fromtimestamp(
        1577941200, tz=pytz.timezone("US/Eastern")
    )
    assert candles[0].Open == 74.06
    assert candles[0].High == 75.15
    assert candles[0].Low == 73.7975
    assert candles[0].Close == 75.0875
    assert candles[0].Volume == 135647456


def test_get_stocks_candles_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("stocks_candles_response_200")

        respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )

        candles = client.stocks.candles(
            symbol="AAPL",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
        )
        assert len(candles) == 253
        assert candles.index[0] == datetime.datetime.fromtimestamp(
            1577941200, tz=pytz.timezone("US/Eastern")
        )
        assert candles.o.tolist()[0] == 74.06
        assert candles.h.tolist()[0] == 75.15
        assert candles.l.tolist()[0] == 73.7975
        assert candles.c.tolist()[0] == 75.0875
        assert candles.v.tolist()[0] == 135647456


def test_get_stocks_candles_response_200_dataframe_polars(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("stocks_candles_response_200")

        respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )
        candles = client.stocks.candles(
            symbol="AAPL",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
        )
        assert len(candles) == 253
        assert candles["t"][0] == datetime.datetime.fromtimestamp(
            1577941200, tz=pytz.timezone("US/Eastern")
        )
        assert candles["o"][0] == 74.06
        assert candles["h"][0] == 75.15
        assert candles["l"][0] == 73.7975
        assert candles["c"][0] == 75.0875
        assert candles["v"][0] == 135647456


def test_get_stocks_candles_response_200_dataframe_pandas_spreadsheet_dateformat(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = copy.deepcopy(load_json("stocks_candles_response_200"))
        epoch = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
        mock_data["t"] = [
            (
                datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc) - epoch
            ).total_seconds()
            / 86400
            for ts in mock_data["t"]
        ]

        respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )

        candles = client.stocks.candles(
            symbol="AAPL",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
            date_format=DateFormat.SPREADSHEET,
        )
        assert len(candles) == 253
        assert int(candles.index[0].timestamp()) == 1577941200


def test_get_stocks_candles_response_200_dataframe_polars_spreadsheet_dateformat(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = copy.deepcopy(load_json("stocks_candles_response_200"))
        epoch = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)
        mock_data["t"] = [
            (
                datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc) - epoch
            ).total_seconds()
            / 86400
            for ts in mock_data["t"]
        ]

        respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )
        candles = client.stocks.candles(
            symbol="AAPL",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
            date_format=DateFormat.SPREADSHEET,
        )
        assert len(candles) == 253
        assert int(candles["t"][0].timestamp()) == 1577941200


def test_get_stocks_candles_response_bad_status_code(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json={"errmsg": "Test error message"},
        status_code=501,
    )

    with pytest.raises(ServerError) as exc_info:
        client.stocks.candles(symbol="AAPL", resolution="D")
    assert exc_info.value.message == "Test error message"


def test_get_stocks_candles_response_200_dataframe_multiple_years_hourly(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/H/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="H",
        from_date=datetime.datetime(2020, 1, 1, tzinfo=pytz.timezone("US/Eastern")),
        to_date=datetime.datetime(2022, 10, 1, tzinfo=pytz.timezone("US/Eastern")),
        output_format=OutputFormat.DATAFRAME,
    )

    assert len(candles) == 253 * 3

    def _validate_candle(index: int, candle: StockCandle):
        assert candles.index[index] == datetime.datetime.fromtimestamp(
            1577941200, tz=pytz.timezone("US/Eastern")
        )
        assert candles.o.tolist()[index] == 74.06
        assert candles.h.tolist()[index] == 75.15
        assert candles.l.tolist()[index] == 73.7975
        assert candles.c.tolist()[index] == 75.0875
        assert candles.v.tolist()[index] == 135647456

    _validate_candle(0, candles.iloc[0])

    second_year_first_candle = 253
    _validate_candle(second_year_first_candle, candles.iloc[second_year_first_candle])

    third_year_first_candle = 253 * 2
    _validate_candle(third_year_first_candle, candles.iloc[third_year_first_candle])


def test_get_stocks_candles_response_200_dataframe_multiple_years_daily(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        from_date=datetime.datetime(2020, 1, 1, tzinfo=pytz.timezone("US/Eastern")),
        to_date=datetime.datetime(2022, 10, 1, tzinfo=pytz.timezone("US/Eastern")),
        output_format=OutputFormat.DATAFRAME,
    )

    assert len(candles) == 253
    assert candles.index[0] == datetime.datetime.fromtimestamp(
        1577941200, tz=pytz.timezone("US/Eastern")
    )
    assert candles.o.tolist()[0] == 74.06
    assert candles.h.tolist()[0] == 75.15
    assert candles.l.tolist()[0] == 73.7975
    assert candles.c.tolist()[0] == 75.0875
    assert candles.v.tolist()[0] == 135647456


def test_get_stocks_candles_response_200_dataframe_multiple_years_daily_no_to_date(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        from_date=datetime.datetime(2020, 1, 1),
        output_format=OutputFormat.DATAFRAME,
    )

    assert len(candles) == 253
    assert respx_mock.calls.last.request.url.params.get("to") is None


def test_get_stocks_candles_response_200_dataframe_multiple_years_hourly_no_to_date(
    load_json, respx_mock, client
):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/H/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    with freeze_time("2023-01-01"):
        candles = client.stocks.candles(
            symbol="AAPL",
            resolution="H",
            from_date=datetime.datetime(
                2020, 1, 10, tzinfo=pytz.timezone("US/Eastern")
            ),
            output_format=OutputFormat.DATAFRAME,
        )

    assert len(candles) == 253 * 3
    assert respx_mock.calls.last.request.url.params.get("to") is not None


def test_get_stocks_candles_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/stocks/candles/"],
        "status": ["offline"],
        "online": [False],
        "uptimePct30d": [0],
        "uptimePct90d": [0],
        "updated": [0],
    }
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json=mock_data,
        status_code=200,
    )

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/D/AAPL/").respond(
        json={},
        status_code=501,
    )

    with pytest.raises(ServerError):
        client.stocks.candles(
            symbol="AAPL",
            resolution="D",
            output_format=OutputFormat.INTERNAL,
        )


# ------------------------------------------------------------------- CSV

DAILY_URL = "https://api.marketdata.app/v1/stocks/candles/D/AAPL/"
HOURLY_URL = "https://api.marketdata.app/v1/stocks/candles/H/AAPL/"
CSV_BODY = (
    "t,o,h,l,c,v\r\n"
    "1704171600,185.6,186.88,182.36,184.1,82488674\r\n"
    "1704258000,182.69,184.34,181.91,182.72,58414460\r\n"
)
CSV_PLACEHOLDER = '0\r\n""\r\n'
TWO_CHUNKS = dict(from_date="2023-01-01", to_date="2024-06-01")
CHUNK_STARTS = ["2023-01-01", "2024-01-01"]


def by_chunk(*responses: dict):
    """Answer each chunk by its `from` date rather than by call order.

    The chunks are fetched in parallel, so a plain `side_effect=[a, b]` hands
    the first body to whichever worker the pool happened to start first: the
    merge then came out in either order and the assertions raced. Keyed on the
    chunk start, each chunk always gets its own body. Each call builds a fresh
    `httpx.Response`, since a retried chunk asks for the same one twice.
    """
    by_start = dict(zip(CHUNK_STARTS, responses))

    def answer(request):
        return httpx.Response(200, **by_start[request.url.params["from"][:10]])

    return answer


def test_get_stocks_candles_response_200_csv(respx_mock, client, tmp_path):
    """The file is the API's CSV as received: its header, its rows."""
    respx_mock.get(DAILY_URL).respond(text=CSV_BODY, status_code=200)

    output = client.stocks.candles(
        symbol="AAPL",
        resolution="D",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
    )

    assert pathlib.Path(output).read_bytes() == CSV_BODY.encode()


def test_stocks_candles_csv_merges_every_chunk_under_the_api_header(
    respx_mock, client, tmp_path
):
    respx_mock.get(HOURLY_URL).mock(
        side_effect=by_chunk(dict(text="t,c\r\n1,2\r\n"), dict(text="t,c\r\n3,4\r\n"))
    )

    output = client.stocks.candles(
        symbol="AAPL",
        resolution="H",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
        columns=["t", "c"],
        **TWO_CHUNKS,
    )

    assert pathlib.Path(output).read_bytes() == b"t,c\r\n1,2\r\n3,4\r\n"


def test_stocks_candles_csv_undecodable_chunk_body_is_a_parse_error(
    respx_mock, client, tmp_path
):
    """Issue #86: an HTML page from one chunk fails the call instead of
    leaving a hole in the file."""
    respx_mock.get(HOURLY_URL).mock(
        side_effect=by_chunk(dict(text=CSV_BODY), dict(text="<html>error page</html>"))
    )

    with pytest.raises(ParseError):
        client.stocks.candles(
            symbol="AAPL",
            resolution="H",
            output_format=OutputFormat.CSV,
            filename=tmp_path / "test.csv",
            **TWO_CHUNKS,
        )

    assert not (tmp_path / "test.csv").exists()


def test_stocks_candles_csv_chunk_the_csv_module_cannot_read_is_a_parse_error(
    respx_mock, client, tmp_path
):
    """Issue #86: a field past the csv reader's limit escaped as a raw
    `csv.Error`, which is not an SDK exception."""
    unreadable = CSV_BODY + "x" * 200_000 + ",1,1,1,1,1\r\n"
    respx_mock.get(HOURLY_URL).mock(
        side_effect=by_chunk(dict(text=CSV_BODY), dict(text=unreadable))
    )

    with pytest.raises(ParseError) as exc_info:
        client.stocks.candles(
            symbol="AAPL",
            resolution="H",
            output_format=OutputFormat.CSV,
            filename=tmp_path / "test.csv",
            **TWO_CHUNKS,
        )

    assert "unreadable CSV" in exc_info.value.message
    assert "from=2024-01-01" in exc_info.value.request_url
    assert not (tmp_path / "test.csv").exists()


def test_stocks_candles_csv_leaves_out_a_chunk_with_no_data(
    respx_mock, client, tmp_path
):
    """Issue #89: the API's CSV placeholder for an empty chunk is a 200."""
    respx_mock.get(HOURLY_URL).mock(
        side_effect=by_chunk(dict(text=CSV_PLACEHOLDER), dict(text=CSV_BODY))
    )

    output = client.stocks.candles(
        symbol="AAPL",
        resolution="H",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
        **TWO_CHUNKS,
    )

    assert pathlib.Path(output).read_bytes() == CSV_BODY.encode()


def test_stocks_candles_csv_with_every_chunk_empty_is_a_header_only_file(
    respx_mock, client, tmp_path
):
    respx_mock.get(HOURLY_URL).respond(text=CSV_PLACEHOLDER, status_code=200)

    output = client.stocks.candles(
        symbol="AAPL",
        resolution="H",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
        columns=["t", "c"],
        **TWO_CHUNKS,
    )

    assert pathlib.Path(output).read_bytes() == b"t,c\r\n"


CANDLE_CHUNK = dict(json={"s": "ok", "t": [1], "c": [1.0]})


@pytest.mark.parametrize(
    ("bodies", "bad_index", "reason"),
    [
        (
            [dict(json={"error": "upstream timeout"}), CANDLE_CHUNK],
            0,
            "missing columns ['t', 'c']",
        ),
        ([CANDLE_CHUNK, dict(json={"s": "ok", "t": [2]})], 1, "missing columns ['c']"),
        ([dict(json={"s": "ok", "t": [2]}), CANDLE_CHUNK], 0, "missing columns ['c']"),
        ([CANDLE_CHUNK, dict(json={"t": [2], "c": []})], 1, "different lengths"),
        ([CANDLE_CHUNK, dict(text="null")], 1, "not a JSON object"),
        ([dict(text="[]"), CANDLE_CHUNK], 0, "not a JSON object"),
    ],
    ids=[
        "no-fields-at-all",
        "a-later-chunk-lacks-a-column",
        "the-first-chunk-lacks-a-column",
        "a-chunk-with-an-empty-column",
        "a-chunk-is-null",
        "a-chunk-is-an-array",
    ],
)
def test_stocks_candles_json_chunk_without_the_columns_is_a_parse_error(
    respx_mock, client, bodies, bad_index, reason
):
    """A JSON body without the resource's fields (a proxy's JSON error page)
    fails the call instead of leaving a silent hole in the merge, and so does a
    chunk lacking a column another chunk carries, the first chunk included, or
    carrying one that is shorter than the others. A body that is not an object
    fails for that reason: `null` used to raise a bare `TypeError` from the
    merge (an array already failed, as a body without the fields)."""
    respx_mock.get(HOURLY_URL).mock(side_effect=by_chunk(*bodies))

    with pytest.raises(ParseError) as exc_info:
        client.stocks.candles(
            symbol="AAPL", resolution="H", output_format=OutputFormat.JSON, **TWO_CHUNKS
        )

    assert f"from={CHUNK_STARTS[bad_index]}" in exc_info.value.request_url
    assert reason in exc_info.value.message


# ------------------------------------------------------------- columns=


@pytest.mark.parametrize("output_format", [OutputFormat.DATAFRAME, OutputFormat.JSON])
def test_stocks_candles_honours_the_column_filter_across_chunks(
    respx_mock, client, output_format
):
    """Issue #90: the API answers with the requested keys only; the merge used
    to raise KeyError on the first missing model field."""
    respx_mock.get(HOURLY_URL).mock(
        side_effect=by_chunk(
            dict(json={"s": "ok", "c": [1.0, 2.0], "v": [10, 20]}),
            dict(json={"s": "ok", "c": [3.0], "v": [30]}),
        )
    )

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        result = client.stocks.candles(
            symbol="AAPL",
            resolution="H",
            output_format=output_format,
            columns=["c", "v"],
            **TWO_CHUNKS,
        )

    if output_format == OutputFormat.JSON:
        assert result == {"c": [1.0, 2.0, 3.0], "v": [10, 20, 30]}
    else:
        assert list(result.columns) == ["c", "v"]
        assert result["c"].tolist() == [1.0, 2.0, 3.0]


@pytest.mark.parametrize("handler", ["pandas", "polars"])
def test_stocks_candles_keeps_the_order_the_columns_were_requested_in(
    respx_mock, client, handler
):
    """Checked live: `columns=v,c` answers `{"v": [...], "c": [...]}`, request
    order and no status flag. The merged chunks keep that order, as the empty
    result does (#87): the model's order (`c` before `v`) made the two frames
    disagree, and `pl.concat` refuses frames whose columns differ in order."""
    respx_mock.get(HOURLY_URL).mock(
        side_effect=by_chunk(
            dict(json={"v": [10, 20], "c": [1.0, 2.0]}),
            dict(json={"v": [30], "c": [3.0]}),
        )
    )
    empty_route = respx_mock.get(DAILY_URL).respond(
        json={"s": "no_data"}, status_code=404
    )

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", [handler]):
        populated = client.stocks.candles(
            symbol="AAPL",
            resolution="H",
            output_format=OutputFormat.DATAFRAME,
            columns=["v", "c"],
            **TWO_CHUNKS,
        )
        empty = client.stocks.candles(
            symbol="AAPL",
            resolution="D",
            output_format=OutputFormat.DATAFRAME,
            columns=["v", "c"],
        )
        merged_json = client.stocks.candles(
            symbol="AAPL",
            resolution="H",
            output_format=OutputFormat.JSON,
            columns=["v", "c"],
            **TWO_CHUNKS,
        )

    assert empty_route.called
    assert list(populated.columns) == list(empty.columns) == ["v", "c"]
    assert list(merged_json) == ["v", "c"]


def test_stocks_candles_intraday_string_dates(load_json, respx_mock, client):
    mock_data = load_json("stocks_candles_response_200")

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/4H/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    candles = client.stocks.candles(
        symbol="AAPL",
        resolution="4H",
        from_date="2023-01-01",
        to_date="2023-01-05",
        output_format=OutputFormat.INTERNAL,
    )
    assert len(candles) == 253


def _wire_ranges(respx_mock) -> list[tuple[datetime.date, datetime.date]]:
    ranges = []
    for call in respx_mock.calls:
        params = call.request.url.params
        if "from" in params:
            ranges.append(
                (
                    datetime.date.fromisoformat(params["from"]),
                    datetime.date.fromisoformat(params["to"]),
                )
            )
    return sorted(ranges)


def test_stocks_candles_intraday_chunks_never_share_a_day_on_the_wire(
    load_json, respx_mock, client
):
    """Issue #51: the API treats a date-only `to=` as inclusive, so the day
    that closes one chunk must not open the next one."""
    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/H/AAPL/").respond(
        json=load_json("stocks_candles_response_200"), status_code=200
    )
    start, end = datetime.date(2020, 1, 1), datetime.date(2022, 10, 1)

    client.stocks.candles(
        "AAPL",
        resolution="H",
        from_date=start,
        to_date=end,
        output_format=OutputFormat.JSON,
    )

    ranges = _wire_ranges(respx_mock)
    assert len(ranges) == 3
    assert ranges[0][0] == start
    assert ranges[-1][1] == end
    for (_, previous_to), (next_from, _) in zip(ranges, ranges[1:]):
        assert next_from == previous_to + datetime.timedelta(days=1)


def test_stocks_candles_intraday_inclusive_api_yields_each_day_once(respx_mock, client):
    """Regression for #51 against an API double that, like the real one,
    returns every candle of the `to=` day. Before the fix each boundary day
    came back twice in the merged result."""

    def _one_candle_per_day(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        first = datetime.date.fromisoformat(params["from"])
        last = datetime.date.fromisoformat(params["to"])
        stamps = [
            int(
                datetime.datetime.combine(
                    first + datetime.timedelta(days=i),
                    datetime.time(12),
                    tzinfo=datetime.timezone.utc,
                ).timestamp()
            )
            for i in range((last - first).days + 1)
        ]
        n = len(stamps)
        return httpx.Response(
            200,
            json={
                "s": "ok",
                "t": stamps,
                "o": [1.0] * n,
                "h": [1.0] * n,
                "l": [1.0] * n,
                "c": [1.0] * n,
                "v": [1] * n,
            },
        )

    respx_mock.get("https://api.marketdata.app/v1/stocks/candles/H/AAPL/").mock(
        side_effect=_one_candle_per_day
    )
    start, end = datetime.date(2020, 1, 1), datetime.date(2022, 10, 1)

    data = client.stocks.candles(
        "AAPL",
        resolution="H",
        from_date=start,
        to_date=end,
        output_format=OutputFormat.JSON,
    )

    expected_days = (end - start).days + 1
    assert len(data["t"]) == expected_days
    assert len(set(data["t"])) == expected_days
