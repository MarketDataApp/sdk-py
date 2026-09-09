import datetime

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
    merge_csv_responses,
    obfuscate_token,
    parse_csv_errmsg,
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
    assert check_is_date("2024-01-01") == True
    assert check_is_date(datetime.date(2024, 1, 1)) == True
    assert check_is_date(None) == False
    assert check_is_date("yesterday") == False
    assert check_is_date(Exception) == False


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
        # Not a CSV at all: the reader raises on a NUL byte, and an error
        # envelope is never this big.
        ("oops\x00page", None),
        ("s,errmsg\r\nerror," + "a" * 5000 + "\r\n", None),
    ],
)
def test_parse_csv_errmsg_reads_only_the_api_error_table(body, expected):
    """Issue #91: `format=csv` renders an error as `s,errmsg` and one row."""
    assert parse_csv_errmsg(body) == expected


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
