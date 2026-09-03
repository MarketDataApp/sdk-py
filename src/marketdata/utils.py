import csv
import datetime
from enum import Enum
from io import StringIO
from typing import Any
from urllib.parse import quote

import pytz


def format_timestamp(value: str | int | float | None) -> datetime.datetime:
    default_tz = pytz.timezone("US/Eastern")

    if isinstance(value, str):
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(value)
            return dt.astimezone(default_tz) if dt.tzinfo else dt
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                raise ValueError("Unrecognized date format")

    if isinstance(value, (int, float)):
        if 0 < value < 60000:
            return datetime.datetime(1899, 12, 30) + datetime.timedelta(days=value)
        try:
            return datetime.datetime.fromtimestamp(value, tz=default_tz)
        except (ValueError, OSError, OverflowError):
            pass

    raise ValueError("Unrecognized date format")


def check_is_date(value: datetime.date | str | None) -> bool:
    if value is None:
        return False
    if isinstance(value, datetime.date):
        return True
    if isinstance(value, str):
        return "-" in value or "/" in value
    return False


def validate_single_param(param: str, value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return ",".join(str(validate_single_param(param, v)) for v in value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d")
    return value


def merge_csv_texts(csv_texts: list[str], headers: list[str]) -> str:
    rows_out = []

    def _validate(rows: list[list[str]]) -> bool:
        return all(len(row) == len(headers) for row in rows)

    for text in csv_texts:
        reader = csv.reader(StringIO(text))

        try:
            incoming_header = next(reader)
        except StopIteration:
            continue

        if incoming_header != headers:
            continue

        rows = list(reader)
        if _validate(rows):
            rows_out.extend(rows)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows_out)
    return output.getvalue()


_ONE_DAY = datetime.timedelta(days=1)


def _start_of_day(day: datetime.date, like: datetime.datetime) -> datetime.datetime:
    return datetime.datetime.combine(day, datetime.time.min, tzinfo=like.tzinfo)


def split_dates_by_timeframe(
    start: datetime.datetime,
    end: datetime.datetime,
    timeframe: datetime.timedelta,
) -> list[tuple[datetime.datetime, datetime.datetime]]:
    """Split ``[start, end]`` into consecutive ranges of at most ``timeframe`` days.

    The ranges never share a calendar day: each one ends the day before the
    next starts. ``from``/``to`` travel on the wire as dates and the API treats
    ``to`` as inclusive, so two ranges sharing a boundary day would fetch that
    day twice (#51). The first range keeps ``start`` and the last keeps ``end``
    untouched; interior boundaries are midnight in the timezone of ``start``.
    """
    if start > end:
        raise ValueError("start must not be after end")
    if timeframe < _ONE_DAY:
        raise ValueError("timeframe must be at least one day")

    end_day = end.date()
    ranges: list[tuple[datetime.datetime, datetime.datetime]] = []
    range_start = start

    while True:
        last_day = range_start.date() + timeframe - _ONE_DAY
        if last_day >= end_day:
            ranges.append((range_start, end))
            break
        ranges.append((range_start, _start_of_day(last_day, start)))
        range_start = _start_of_day(last_day + _ONE_DAY, start)

    return ranges


def resume_long_text(text: str, max_length: int = 100) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def get_data_records(data: dict, exclude_keys: list[str] = None) -> list[dict]:
    exclude_keys = exclude_keys or []

    keys = [k for k in data if k not in exclude_keys]

    values = []
    max_len = max(
        len(v) if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)) else 1
        for v in (data[k] for k in keys)
    )

    for k in keys:
        v = data[k]
        if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
            values.append(v)
        else:
            values.append([v] * max_len)

    return [dict(zip(keys, row)) for row in zip(*values)]


def format_duration_log(duration_ms: float) -> str:
    if duration_ms < 1000:
        return f"{int(duration_ms):03d}ms"
    elif duration_ms < 10000:
        return f"{duration_ms / 1000:.2f}s"
    elif duration_ms < 100000:
        return f"{duration_ms / 1000:04.1f}s"
    return f"{duration_ms / 1000:.0f}s".rjust(5)


def obfuscate_token(token: str) -> str:
    # Fixed-width mask so the log output never reveals the token length,
    # and the last 4 chars are only shown when they are a small fraction of the token.
    if not isinstance(token, str):
        return str(token)
    if len(token) <= 8:
        return "****"
    return "****" + token[-4:]


def encode_path_segment(value: Any) -> str:
    # Percent-encode a single URL path segment so caller-supplied input
    # (e.g. a symbol) cannot smuggle extra path segments ("AAPL/../../user"),
    # query params or fragments into the request. Valid symbols
    # (alphanumerics, ".", "-", "_") are unaffected.
    return quote(str(value), safe="")


def encode_path(value: str) -> str:
    # Percent-encode a multi-segment URL path (e.g. an options lookup string,
    # where "/" is valid inside dates). Literal slashes are kept, but
    # dot-segments ("." / "..") are neutralized so caller-supplied input
    # cannot traverse to a different endpoint.
    quoted = quote(str(value))
    segments = [
        s.replace(".", "%2E") if s and s.strip(".") == "" else s
        for s in quoted.split("/")
    ]
    return "/".join(segments)
