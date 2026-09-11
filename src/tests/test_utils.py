import csv
import datetime
import sys

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
    resume_long_text,
    split_dates_by_timeframe,
    validate_single_param,
)


def test_format_timestamp():
    # format_timestamp returns naive datetime for string ISO format inputs
    assert format_timestamp("2024-01-01 12:00:00") == datetime.datetime(
        2024, 1, 1, 12, 0, 0
    )
    assert format_timestamp(1714732800) == datetime.datetime.fromtimestamp(
        1714732800, tz=pytz.timezone("US/Eastern")
    )
    assert format_timestamp(1714732800.0) == datetime.datetime.fromtimestamp(
        1714732800, tz=pytz.timezone("US/Eastern")
    )
    # Test 'Z' suffix for Python < 3.11 compatibility
    # Construct expected datetime using localize to avoid pytz LMT issues
    expected_z = pytz.timezone("US/Eastern").localize(
        datetime.datetime(2024, 1, 1, 7, 0, 0)
    )
    assert format_timestamp("2024-01-01T12:00:00Z") == expected_z

    with pytest.raises(ValueError):
        format_timestamp("2024-01-01 12:00:00.0:00:00")
    # Coverage for line 21-23 (string that's not float)
    with pytest.raises(ValueError):
        format_timestamp("invalid-date")
    # Test numeric exceptions (OSError/OverflowError) - coverage for line 30-31
    with pytest.raises(ValueError):
        format_timestamp(99999999999999)
    # Coverage for line 33 (final fallback)
    with pytest.raises(ValueError):
        # List is not str, int, float, or None
        format_timestamp([])
    with pytest.raises(ValueError):
        format_timestamp(None)


def test_format_timestamp_date_only_localization():
    val = "2026-02-20"
    dt = format_timestamp(val)
    assert dt == datetime.datetime(2026, 2, 20, 0, 0, 0)
    assert dt.tzinfo is None


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
    ["t,c", "T,C", "t, c", "﻿t,c"],
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


# ----------------------------------------------------------- is_no_data

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
