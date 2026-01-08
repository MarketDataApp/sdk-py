import csv
import datetime
from enum import Enum
from io import StringIO
from typing import Any

import pytz


def format_timestamp(value: str | int | float | None) -> datetime.datetime:
    if isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value)
        except:
            pass
        try:
            value = float(value)
        except:
            raise ValueError("Unrecognized date format")

    if isinstance(value, (int, float)):
        if 0 < value < 60000:
            return datetime.datetime(1899, 12, 30) + datetime.timedelta(days=value)
        try:
            return datetime.datetime.fromtimestamp(value, tz=pytz.timezone('US/Eastern'))
        except:
            raise ValueError("Unrecognized date format")

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


def split_dates_by_timeframe(
    start: datetime.datetime,
    end: datetime.datetime,
    timeframe: datetime.timedelta,
) -> list[tuple[datetime.datetime, datetime.datetime]]:
    if start >= end:
        raise ValueError("start must be before end")

    ranges: list[tuple[datetime.datetime, datetime.datetime]] = []
    current = start

    while True:
        next_cut = current + timeframe
        if next_cut >= end:
            ranges.append((current, end))
            break
        ranges.append((current, next_cut))
        current = next_cut

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
