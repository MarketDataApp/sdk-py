import datetime

import pytest
import pytz

from marketdata.input_types.base import DateFormat, OutputFormat
from marketdata.utils import (
    check_is_date,
    encode_path,
    encode_path_segment,
    format_duration_log,
    format_timestamp,
    merge_csv_texts,
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


def test_merge_csv_texts():
    texts = [
        "a,b,c\n1,2,3\n4,5,6",
        "a,b,c\n7,8,9\n10,11,12",
    ]
    result = merge_csv_texts(texts, ["a", "b", "c"])
    assert result == "a,b,c\r\n1,2,3\r\n4,5,6\r\n7,8,9\r\n10,11,12\r\n"

    texts = [
        "a,b,c\n1,2,3\n4,5,6",
        "a,b,c\n7,8,9\n10,11,12",
        "",
    ]
    result = merge_csv_texts(texts, ["a", "b", "c"])
    expected = "a,b,c\r\n1,2,3\r\n4,5,6\r\n7,8,9\r\n10,11,12\r\n"
    assert result == expected

    texts = [
        "a,b,c\n1,2,3\n4,5,6",
        "a,b,c\n7,8,9\n10,11,12",
        "a,b,d\n13,14,15\n16,17,18",
    ]
    result = merge_csv_texts(texts, ["a", "b", "c"])
    expected = "a,b,c\r\n1,2,3\r\n4,5,6\r\n7,8,9\r\n10,11,12\r\n"
    assert result == expected


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
