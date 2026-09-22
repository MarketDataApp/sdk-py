import csv
import datetime
import sys
from decimal import Decimal

import httpx
import pytest
import pytz

from marketdata.exceptions import ParseError
from marketdata.input_types.base import DateFormat, OutputFormat
from marketdata.utils import (
    check_is_date,
    column_key,
    dict_to_csv,
    encode_path,
    encode_path_segment,
    format_duration_log,
    format_timestamp,
    is_no_data,
    json_answer_columns,
    merge_csv_responses,
    obfuscate_token,
    parse_csv_errmsg,
    resume_long_text,
    split_dates_by_timeframe,
    validate_single_param,
)

_EASTERN = pytz.timezone("US/Eastern")


def _eastern(*args: int, is_dst: bool = False) -> datetime.datetime:
    """Build a US/Eastern datetime from its wall-clock fields."""
    return _EASTERN.localize(datetime.datetime(*args), is_dst=is_dst)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # The API's bands (`DateHelper.date_from_number`): a spreadsheet serial
        # from 10000 up to 200000, then Unix seconds, milliseconds, nanoseconds.
        (45000, _eastern(2023, 3, 15)),
        (59999, _eastern(2064, 4, 7)),
        (60000, _eastern(2064, 4, 8)),
        (100000, _eastern(2173, 10, 14)),
        (46286.60208, _eastern(2026, 9, 21, 14, 27)),
        (Decimal("46286.60208"), _eastern(2026, 9, 21, 14, 27)),
        ("46286.60208", _eastern(2026, 9, 21, 14, 27)),
        (1_789_000_000, _eastern(2026, 9, 9, 20, 26, 40)),
        (1_789_000_000_000, _eastern(2026, 9, 9, 20, 26, 40)),
        (1_789_000_000_000_000_000, _eastern(2026, 9, 9, 20, 26, 40)),
        # `dateformat=timestamp` strings, as `DateHelper.format_date` writes them.
        ("2026-09-21 14:02:10 -04:00", _eastern(2026, 9, 21, 14, 2, 10)),
        ("2026-01-15 09:30:00 -05:00", _eastern(2026, 1, 15, 9, 30)),
        ("2026-09-21", _eastern(2026, 9, 21)),
        ("2024-01-01T12:00:00Z", _eastern(2024, 1, 1, 7)),
        ("2024-01-01 12:00:00", _eastern(2024, 1, 1, 12)),
        # A wall time the clocks pass twice is the first one.
        ("2026-11-01 01:30:00", _eastern(2026, 11, 1, 1, 30, is_dst=True)),
    ],
)
def test_format_timestamp_reads_what_the_api_sends(value, expected):
    """Every value comes back as the US/Eastern datetime it names."""
    result = format_timestamp(value)

    assert result == expected
    assert result.utcoffset() == expected.utcoffset()


@pytest.mark.parametrize(
    "value",
    [
        60,
        5000,
        -5,
        -10000,
        9999.9,
        "60",
        True,
        "invalid-date",
        "2024-01-01 12:00:00.0:00:00",
        "nan",
        float("inf"),
        [],
        None,
    ],
)
def test_format_timestamp_refuses_what_is_not_a_date(value):
    """A number under 10000 is a relative range for the API, not a date, and
    anything else that is not a date raises too."""
    with pytest.raises(ValueError, match="Unrecognized date format"):
        format_timestamp(value)


def test_format_timestamp_keeps_a_datetime():
    """A datetime is already a date: it comes back as it is."""
    moment = datetime.datetime(2026, 9, 21, 14, 2)

    assert format_timestamp(moment) is moment


def test_check_is_date():
    assert check_is_date("2024-01-01")
    assert check_is_date(datetime.date(2024, 1, 1))
    assert not check_is_date(None)
    assert not check_is_date("yesterday")
    assert not check_is_date(Exception)


def test_validate_single_param():
    assert validate_single_param("a", 1) == 1
    assert validate_single_param("a", [1, 2, 3]) == "1,2,3"
    assert validate_single_param("a", OutputFormat.DATAFRAME) == "dataframe"
    assert validate_single_param("a", DateFormat.UNIX) == "unix"
    assert validate_single_param("a", datetime.datetime(2024, 1, 1)) == "2024-01-01"
    assert validate_single_param("a", True) == "true"
    assert validate_single_param("a", False) == "false"
    assert validate_single_param("a", None) is None


# ----------------------------------------------------- merge_csv_responses

COLUMNS = ["t", "o", "h", "l", "c", "v"]


def _csv_response(text: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        text=text,
        request=httpx.Request("GET", "https://api.marketdata.app/v1/x/"),
    )


def test_merge_csv_responses_takes_the_header_from_the_answers():
    """Issue #86: the merged header is the one the API sent, so `columns=`
    and the human-readable names survive the merge, with every row."""
    responses = [
        _csv_response("t,c\n1,2\n3,4\n"),
        _csv_response("t,c\r\n5,6\r\n"),
        _csv_response("t,c\n"),
    ]

    assert merge_csv_responses(responses, COLUMNS) == "t,c\r\n1,2\r\n3,4\r\n5,6\r\n"


def test_merge_csv_responses_accepts_human_readable_names_for_the_model_fields():
    responses = [_csv_response("\ufeffExpiration Date,Strike\n1,2\n")]

    result = merge_csv_responses(responses, ["Expiration_Date", "Strike"])

    assert result == "Expiration Date,Strike\r\n1,2\r\n"


@pytest.mark.parametrize(
    ("bodies", "reason"),
    [
        (["<html>error page</html>\n"], "unknown columns"),
        ([""], "no header row"),
        (["t,c\n1,2\n", "t,o\n1,2\n"], "differs from"),
        (["t,c\n1,2\n", "t,c\n1\n"], "does not have 2 values"),
    ],
)
def test_merge_csv_responses_rejects_a_body_that_is_not_this_resource(bodies, reason):
    responses = [_csv_response(body) for body in bodies]

    with pytest.raises(ParseError) as exc_info:
        merge_csv_responses(responses, COLUMNS)

    assert reason in exc_info.value.message
    assert exc_info.value.response is responses[-1]


@pytest.mark.parametrize(
    "second_header",
    ["t,c", "T,C", "t, c", "\ufefft,c"],
    ids=["identical", "different-case", "space-after-comma", "bom"],
)
def test_merge_csv_responses_compares_headers_the_way_it_validates_them(second_header):
    """A header is accepted when its names are this resource's columns seen
    through `column_key`; the comparison between answers uses the same key, so
    the same column spelled differently still merges. Raising here would be a
    `ParseError` on a valid request, the failure mode #86 set out to remove.
    The file keeps the first answer's spelling."""
    responses = [_csv_response("t,c\n1,2\n"), _csv_response(f"{second_header}\n3,4\n")]

    assert merge_csv_responses(responses, COLUMNS) == "t,c\r\n1,2\r\n3,4\r\n"


def test_merge_csv_responses_still_refuses_a_different_column_order():
    """Columns in another order are not the same header: merging the rows
    would put each value under the wrong column."""
    responses = [_csv_response("t,c\n1,2\n"), _csv_response("c,t\n4,3\n")]

    with pytest.raises(ParseError) as exc_info:
        merge_csv_responses(responses, COLUMNS)

    assert "differs from" in exc_info.value.message


def test_merge_csv_responses_drops_a_bom_from_every_body_with_or_without_a_header():
    """A BOM is not data. Without a header it stayed in the first value of
    each body, and so in the middle of the merged file. The API sends none
    today (checked live, with and without headers); a proxy might."""
    with_header = [
        _csv_response("\ufefft,c\n1,2\n"),
        _csv_response("\ufefft,c\n3,4\n"),
    ]
    without = [
        _csv_response("\ufeff1,2\n"),
        _csv_response("\ufeff3,4\n"),
    ]

    assert merge_csv_responses(with_header, COLUMNS) == "t,c\r\n1,2\r\n3,4\r\n"
    assert merge_csv_responses(without, COLUMNS, with_header=False) == (
        "1,2\r\n3,4\r\n"
    )
    # A BOM does not break the quoting of the first value either.
    quoted = [_csv_response('\ufeff"1",2\n')]
    assert merge_csv_responses(quoted, COLUMNS, with_header=False) == "1,2\r\n"
    # Only at the start of a body: a U+FEFF inside a value, or at the start of a
    # later row, is data.
    inside = [_csv_response("1,\ufeff2\n\ufeff3,4\n")]
    assert merge_csv_responses(inside, COLUMNS, with_header=False) == (
        "1,\ufeff2\r\n\ufeff3,4\r\n"
    )


def test_merge_csv_responses_reads_a_body_whose_lines_end_in_a_lone_cr():
    """Old Mac line endings are rows, not a body the reader refuses. The merged
    file is written with the standard CRLF, as every merge is."""
    responses = [_csv_response("t,c\r1,2\r"), _csv_response("t,c\r3,4\r")]

    assert merge_csv_responses(responses, COLUMNS) == "t,c\r\n1,2\r\n3,4\r\n"


def test_merge_csv_responses_without_headers_concatenates_rows_of_one_width():
    responses = [_csv_response("1,2\n3,4\n"), _csv_response("5,6\n")]

    result = merge_csv_responses(responses, COLUMNS, with_header=False)

    assert result == "1,2\r\n3,4\r\n5,6\r\n"
    with pytest.raises(ParseError):
        merge_csv_responses(
            responses + [_csv_response("7\n")], COLUMNS, with_header=False
        )


# A field past the reader's limit fails on every Python; a NUL byte only
# before 3.11, which reads it as data.
UNREADABLE_CSV_FIELDS = [
    pytest.param("x" * 200_000, id="field-over-the-limit"),
    pytest.param(
        "a\x00b",
        id="nul-byte",
        marks=pytest.mark.skipif(
            sys.version_info >= (3, 11), reason="the csv module reads NUL from 3.11 on"
        ),
    ),
]


@pytest.mark.parametrize("with_header", [True, False], ids=["header", "no-header"])
@pytest.mark.parametrize("field", UNREADABLE_CSV_FIELDS)
def test_merge_csv_responses_turns_a_body_the_csv_module_cannot_read_into_a_parse_error(
    field, with_header
):
    """`csv.Error` is not an SDK exception: a body the reader refuses fails
    like any other body that is not this resource's answer, and names it."""
    header = "t,c\n" if with_header else ""
    responses = [
        _csv_response(f"{header}1,2\n"),
        _csv_response(f"{header}{field},3\n"),
    ]

    with pytest.raises(ParseError) as exc_info:
        merge_csv_responses(responses, COLUMNS, with_header=with_header)

    assert "unreadable CSV" in exc_info.value.message
    assert exc_info.value.response is responses[1]
    assert isinstance(exc_info.value.__cause__, csv.Error)


# ----------------------------------------------------- json_answer_columns


def test_json_answer_columns_follow_the_order_the_answers_send():
    """Under `columns=` the API sends the requested keys only, in request
    order (checked live: `columns=v,c` answers `{"v": [...], "c": [...]}`).
    The merge keeps that order, which is the order of the empty result and of
    every single-request resource, not the model's; the status flag and keys
    the model does not know are not columns."""
    responses = [_csv_response(""), _csv_response("")]
    answers = [{"c": [1], "t": [2], "x": [0]}, {"c": [4], "t": [3], "s": "ok"}]

    assert json_answer_columns(responses, answers, COLUMNS) == ["c", "t"]


@pytest.mark.parametrize(
    ("answers", "reason", "bad_index"),
    [
        ([{"t": [1]}, None], "not a JSON object", 1),
        ([[], {"t": [1]}], "not a JSON object", 0),
        ([{"t": [1]}, "t"], "not a JSON object", 1),
        (
            [{"s": "ok", "error": "upstream timeout"}],
            "none of this resource's fields",
            0,
        ),
        ([{"t": [1], "c": [2]}, {"t": [3], "c": [4]}, {"t": [5]}], "['c']", 2),
        ([{"t": [1]}, {"t": [3], "c": [4]}], "missing columns ['c']", 0),
        ([{"t": [1], "c": [2]}, {"t": [3], "c": []}], "different lengths", 1),
        ([{"t": [1], "c": [2]}, {"t": [3], "c": "4.5"}], "are not lists", 1),
        ([{"t": [1], "c": [2]}, {"t": [3], "c": None}], "are not lists", 1),
    ],
    ids=[
        "null",
        "array",
        "string",
        "no-columns",
        "a-later-answer-lacks-one",
        "the-first-answer-lacks-one",
        "an-empty-column",
        "a-column-that-is-a-string",
        "a-null-column",
    ],
)
def test_json_answer_columns_name_the_answer_that_breaks_the_merge(
    answers, reason, bad_index
):
    """The review of #92: a column missing from one symbol shifted the rows of
    every symbol after it. Whichever answer lacks a column, the first one
    included, fails the call, and so does a column that is empty or not a
    list, which shifts the rows the same way. Each failure is a `ParseError`
    carrying the response that caused it."""
    responses = [_csv_response("") for _ in answers]

    with pytest.raises(ParseError) as exc_info:
        json_answer_columns(responses, answers, COLUMNS)

    assert reason in exc_info.value.message
    assert exc_info.value.response is responses[bad_index]


def test_column_key_matches_names_the_way_the_api_does():
    assert column_key("Expiration Date") == column_key("Expiration_Date")
    assert column_key("optionSymbol") == column_key("OPTIONSYMBOL")
    assert column_key("t") != column_key("c")


# -------------------------------------------------------- parse_csv_errmsg


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("s,errmsg\r\nno_data,Symbol not found.\r\n", "Symbol not found."),
        (
            's,errmsg\r\nerror,"Bad parameters, see the docs."\r\n',
            "Bad parameters, see the docs.",
        ),
        ("s,errmsg\nerror,Invalid date\n", "Invalid date"),
        ("S,ERRMSG\r\nerror,Invalid date\r\n", "Invalid date"),
        ("s,errmsg\r\nerror,\r\n", ""),
        ("\ufeffs,errmsg\r\nerror,Invalid date\r\n", "Invalid date"),
        # `add_headers=False` drops the header row (verified live), so the
        # values arrive alone and the `s` value is what marks them as an error.
        ("no_data,Symbol not found.\r\n", "Symbol not found."),
        ("error,Invalid date\r\n", "Invalid date"),
        ("\ufeffno_data,Symbol not found.\r\n", "Symbol not found."),
        # A BOM does not break the quoting of the first value, and one that
        # follows a blank line is dropped after the parse instead.
        ('\ufeff"no_data","Symbol not found."\r\n', "Symbol not found."),
        ("\r\n\ufeffno_data,Symbol not found.\r\n", "Symbol not found."),
        # Lines ending in a lone CR (old Mac style) are rows, not one line the
        # reader refuses. The API sends CRLF; something in between may not.
        ("s,errmsg\rerror,Invalid date\r", "Invalid date"),
        ("no_data,Symbol not found.\r", "Symbol not found."),
        # The marker is matched through `column_key`, as the header row is:
        # normalising one and not the other would drop the message of a 404
        # and read it as the empty answer again.
        ("NO_DATA,Symbol not found.\r\n", "Symbol not found."),
        (" no_data ,Symbol not found.\r\n", "Symbol not found."),
        ("Error,Invalid date\r\n", "Invalid date"),
        # The reader is lenient with an unterminated quote, and reading the
        # message it does recover beats reporting the raw body.
        ('s,errmsg\r\nerror,"Invalid date', "Invalid date"),
        # Not the error envelope: a data answer, an HTML page, an empty body,
        # the no_data placeholder, a header with no row, more than one row.
        ("t,c\r\n1,2\r\n", None),
        ("<html>error page</html>", None),
        ("", None),
        ('0\r\n""\r\n', None),
        ("s,errmsg\r\n", None),
        ("s,errmsg\r\nerror,one\r\nerror,two\r\n", None),
        ("s,errmsg,extra\r\nerror,one,two\r\n", None),
        # A headerless data row is not an error, whatever its width.
        ("1704171600,184.1\r\n", None),
        ("no_data\r\n", None),
        # Not an error table: the reader raises on a NUL byte before Python
        # 3.11 and reads it as data after, and an error envelope is never
        # this big.
        ("oops\x00page", None),
        ("s,errmsg\r\nerror," + "a" * 5000 + "\r\n", None),
    ],
)
def test_parse_csv_errmsg_reads_only_the_api_error_table(body, expected):
    """Issue #91: `format=csv` renders an error as `s,errmsg` and one row."""
    assert parse_csv_errmsg(body) == expected


def test_parse_csv_errmsg_reports_no_table_when_the_reader_refuses_the_body():
    """A body the reader refuses is not an error table: letting `csv.Error` out
    of here would replace the SDK's exception for that request, and a retryable
    status would stop being retried. The NUL byte above only raises before
    Python 3.11, and an envelope is capped well under the reader's field size
    limit, so the limit is lowered here to reach the branch on every version."""
    limit = csv.field_size_limit(16)
    try:
        assert parse_csv_errmsg("s,errmsg\r\nerror," + "a" * 32 + "\r\n") is None
    finally:
        csv.field_size_limit(limit)


# ----------------------------------------------------------- is_no_data

# Built here, not imported from utils, so a wrong constant there fails these tests.
BOM = chr(0xFEFF)

CSV_HEADERS = {"content-type": "text/csv; charset=utf-8"}


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (404, '{"s": "no_data"}', True),
        (200, '0\r\n""\r\n', True),
        (203, '0\r\n""\r\n', True),
        (200, '""\r\n', True),
        (200, '0\n""\n', True),
        (200, "t,c\r\n1,2\r\n", False),
        (200, "0\r\n", False),
        (200, "", False),
        (500, '0\r\n""\r\n', False),
        # A byte order mark in front of the placeholder.
        (200, BOM + '0\r\n""\r\n', True),
        (200, BOM + '""\r\n', True),
        (203, BOM + '0\r\n""\r\n', True),
        # The size limit is measured after the leading marks: 15 bytes of blank
        # lines and placeholder are the empty answer with or without them.
        (200, "\r\n" * 4 + '0\r\n""\r\n', True),
        (200, BOM + "\r\n" * 4 + '0\r\n""\r\n', True),
        (200, BOM + BOM + "\r\n" * 4 + '0\r\n""\r\n', True),
        (200, "\r\n" * 5 + '0\r\n""\r\n', False),
        (200, BOM + "\r\n" * 5 + '0\r\n""\r\n', False),
        # A mark inside a value is data, and so is one that does not open the body.
        (200, '0\r\n"' + BOM + '"\r\n', False),
        (200, "0\r\n" + BOM + '""\r\n', False),
    ],
)
def test_is_no_data_recognises_the_404_and_the_csv_placeholder(status, body, expected):
    """Issue #89: in CSV format the API renders the empty answer as a 200 with
    a placeholder table (MarketData-App/api#422)."""
    assert is_no_data(_csv_response(body, status)) is expected


ET = pytz.timezone("US/Eastern")


def _days_between(first: datetime.date, last: datetime.date) -> list[datetime.date]:
    return [first + datetime.timedelta(days=i) for i in range((last - first).days + 1)]


def test_split_dates_by_timeframe():
    start = datetime.datetime(2024, 1, 1, tzinfo=ET)
    end = datetime.datetime(2024, 1, 31, tzinfo=ET)
    result = split_dates_by_timeframe(start, end, datetime.timedelta(days=1))

    # 31 calendar days, one range each: a range ends on the day it starts and
    # the next one begins the following day (#51).
    assert len(result) == 31
    assert result[0] == (start, datetime.datetime(2024, 1, 1, tzinfo=ET))
    assert result[1] == (
        datetime.datetime(2024, 1, 2, tzinfo=ET),
        datetime.datetime(2024, 1, 2, tzinfo=ET),
    )
    assert result[-1] == (datetime.datetime(2024, 1, 31, tzinfo=ET), end)


def test_split_dates_by_timeframe_ranges_are_disjoint_and_contiguous():
    start = datetime.datetime(2020, 1, 1, tzinfo=ET)
    end = datetime.datetime(2022, 10, 1, tzinfo=ET)
    result = split_dates_by_timeframe(start, end, datetime.timedelta(days=365))

    assert len(result) == 3
    assert result[0][0] == start
    assert result[-1][1] == end
    for (_, previous_end), (next_start, _) in zip(result, result[1:]):
        assert next_start.date() == previous_end.date() + datetime.timedelta(days=1)

    # Every day between start and end is covered exactly once, and no range
    # spans more than the timeframe.
    covered = [set(_days_between(s.date(), e.date())) for s, e in result]
    assert all(len(days) <= 365 for days in covered)
    assert sum(len(days) for days in covered) == len(
        _days_between(start.date(), end.date())
    )
    assert set().union(*covered) == set(_days_between(start.date(), end.date()))


def test_split_dates_by_timeframe_single_range_when_within_timeframe():
    start = datetime.datetime(2024, 1, 1, 9, 30, tzinfo=ET)
    end = datetime.datetime(2024, 3, 1, 16, 0, tzinfo=ET)
    timeframe = datetime.timedelta(days=365)

    assert split_dates_by_timeframe(start, end, timeframe) == [(start, end)]
    # A same-day intraday range is valid and is a single range too.
    assert split_dates_by_timeframe(start, start, timeframe) == [(start, start)]


def test_split_dates_by_timeframe_keeps_caller_instants():
    start = datetime.datetime(2024, 1, 1, 9, 30, tzinfo=ET)
    end = datetime.datetime(2024, 1, 3, 16, 0, tzinfo=ET)
    result = split_dates_by_timeframe(start, end, datetime.timedelta(days=1))

    # The caller's instants survive at both ends; only interior boundaries are
    # generated, at midnight in the caller's timezone.
    assert result[0][0] is start
    assert result[-1][1] is end
    assert result[0][1] == datetime.datetime(2024, 1, 1, tzinfo=ET)
    assert result[1] == (
        datetime.datetime(2024, 1, 2, tzinfo=ET),
        datetime.datetime(2024, 1, 2, tzinfo=ET),
    )


def test_split_dates_by_timeframe_rejects_bad_input():
    start = datetime.datetime(2024, 1, 1, tzinfo=ET)
    end = datetime.datetime(2024, 1, 31, tzinfo=ET)

    with pytest.raises(ValueError):
        split_dates_by_timeframe(end, start, datetime.timedelta(days=1))
    with pytest.raises(ValueError):
        split_dates_by_timeframe(start, end, datetime.timedelta(hours=12))


def test_resume_long_text():
    text = "This is a long text that needs to be shortened"
    assert resume_long_text(text) == "This is a long text that needs to be shortened"
    assert resume_long_text(text, 10) == "This is a ..."
    assert resume_long_text(text, 100) == text
    assert resume_long_text(text, 1000) == text
    assert resume_long_text(text, 10000) == text
    assert resume_long_text(text, 100000) == text
    assert resume_long_text(text, 1000000) == text

    text = text * 1000
    assert resume_long_text(text) == text[:100] + "..."
    assert resume_long_text(text, 10) == text[:10] + "..."
    assert resume_long_text(text, 100) == text[:100] + "..."
    assert resume_long_text(text, 1000) == text[:1000] + "..."
    assert resume_long_text(text, 10000) == text[:10000] + "..."
    assert resume_long_text(text, 100000) == text


def test_format_duration_ms():
    assert format_duration_log(45) == "045ms"
    assert format_duration_log(999) == "999ms"
    assert format_duration_log(0) == "000ms"


def test_format_duration_single_digit_s():
    assert format_duration_log(1230) == "1.23s"
    assert format_duration_log(1000) == "1.00s"
    assert format_duration_log(9990) == "9.99s"


def test_format_duration_double_digit_s():
    assert format_duration_log(12300) == "12.3s"
    assert format_duration_log(10000) == "10.0s"
    assert format_duration_log(99000) == "99.0s"
    assert format_duration_log(99900) == "99.9s"


def test_format_duration_hundred_s():
    assert format_duration_log(100000) == " 100s"


def test_obfuscate_token():
    # Fixed-width mask: never reveals token length
    assert obfuscate_token("1234567890ABCD") == "****ABCD"
    assert obfuscate_token("ABCD") == "****"
    assert obfuscate_token("ABC") == "****"
    assert obfuscate_token("") == "****"
    # Short tokens never reveal any characters
    assert obfuscate_token("12345") == "****"
    assert obfuscate_token("12345678") == "****"
    assert obfuscate_token(None) == "None"


def test_encode_path_segment():
    # Valid symbols pass through unchanged
    assert encode_path_segment("AAPL") == "AAPL"
    assert encode_path_segment("BRK.B") == "BRK.B"
    assert encode_path_segment("AAPL250117C00150000") == "AAPL250117C00150000"
    assert encode_path_segment(5) == "5"
    # Path traversal and query/fragment smuggling are neutralized
    assert encode_path_segment("AAPL/../../user") == "AAPL%2F..%2F..%2Fuser"
    assert encode_path_segment("AAPL?a=b") == "AAPL%3Fa%3Db"
    assert encode_path_segment("AAPL#frag") == "AAPL%23frag"


def test_encode_path():
    # Valid lookup strings keep their slashes, spaces are percent-encoded
    assert encode_path("AAPL 7/28/2023 200 Call") == "AAPL%207/28/2023%20200%20Call"
    # Dot-segments cannot traverse to another endpoint
    assert encode_path("AAPL/../../user") == "AAPL/%2E%2E/%2E%2E/user"
    assert encode_path("..") == "%2E%2E"
    assert encode_path(".") == "%2E"
    # Query/fragment smuggling is neutralized
    assert encode_path("AAPL?a=b#frag") == "AAPL%3Fa%3Db%23frag"


def test_dict_to_csv_column_oriented_payload():
    data = {
        "s": "ok",
        "service": ["/v1/a/", "/v1/b/"],
        "online": [True, False],
        "updated": [1, 2],
    }

    assert dict_to_csv(data, exclude_keys=["s"]) == (
        "service,online,updated\r\n/v1/a/,True,1\r\n/v1/b/,False,2\r\n"
    )


def test_dict_to_csv_flat_object_is_a_single_row():
    data = {"user-agent": "sdk/1.0", "cf-ray": "abc"}

    assert dict_to_csv(data) == "user-agent,cf-ray\r\nsdk/1.0,abc\r\n"


def test_dict_to_csv_empty_payload():
    assert dict_to_csv({}) == ""
