import datetime

import pytest
import pytz

from marketdata.input_types.base import DateFormat, OutputFormat
from marketdata.utils import (
    check_is_date,
    format_timestamp,
    merge_csv_texts,
    resume_long_text,
    split_dates_by_timeframe,
    validate_single_param,
)


def test_format_timestamp():
    # format_timestamp returns naive datetime for string ISO format inputs
    assert format_timestamp("2024-01-01 12:00:00") == datetime.datetime(
        2024, 1, 1, 12, 0, 0
    )
    assert format_timestamp(1714732800) == datetime.datetime.fromtimestamp(1714732800, tz=pytz.timezone('US/Eastern'))
    assert format_timestamp(1714732800.0) == datetime.datetime.fromtimestamp(1714732800, tz=pytz.timezone('US/Eastern'))
    with pytest.raises(ValueError):
        format_timestamp("2024-01-01 12:00:00.0:00:00")
    with pytest.raises(ValueError):
        format_timestamp(99999999999999)
    with pytest.raises(ValueError):
        format_timestamp(None)


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


def test_split_dates_by_timeframe():
    start = datetime.datetime(2024, 1, 1, tzinfo=pytz.timezone('US/Eastern'))
    end = datetime.datetime(2024, 1, 31, tzinfo=pytz.timezone('US/Eastern'))
    timeframe = datetime.timedelta(days=1)
    result = split_dates_by_timeframe(start, end, timeframe)
    assert len(result) == 30

    assert result[0] == (datetime.datetime(2024, 1, 1, tzinfo=pytz.timezone('US/Eastern')), datetime.datetime(2024, 1, 2, tzinfo=pytz.timezone('US/Eastern')))
    assert result[-1] == (
        datetime.datetime(2024, 1, 30, tzinfo=pytz.timezone('US/Eastern')),
        datetime.datetime(2024, 1, 31, tzinfo=pytz.timezone('US/Eastern')),
    )
    with pytest.raises(ValueError):
        split_dates_by_timeframe(end, start, timeframe)


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
