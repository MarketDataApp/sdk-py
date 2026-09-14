import csv
import datetime
from enum import Enum
from io import StringIO
from typing import Any
from urllib.parse import quote

import pytz
from httpx import Response

from marketdata.exceptions import ParseError
from marketdata.internal_settings import VALID_STATUS_CODES


def parse_json(response: Response) -> Any:
    """Decode the response body, or raise ``ParseError`` with support context.

    Every resource decodes through here so an undecodable body is one SDK
    exception (SDK requirements §6.1) instead of a bare ``JSONDecodeError``.
    """
    try:
        return response.json()
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        raise ParseError(
            "Response body is not valid JSON: "
            f"{resume_long_text(response.text, max_length=200)!r}",
            request=response.request,
            response=response,
        ) from exc


# The API's CSV rendering of the empty answer (MarketData-App/api#422): a
# one-column table named "0" with one empty cell, the cell alone under
# ``add_headers=False``. Compared on the non-blank lines of the body. The
# second shape is also what a one-column, one-row answer with a null value
# renders as under ``add_headers=False``; the API itself reports an all-null
# answer as ``no_data`` on the JSON path, so reading it as empty agrees.
_CSV_NO_DATA_BODIES = (["0", '""'], ['""'])


def is_no_data(response: Response) -> bool:
    """True for the API's empty answer to a valid question.

    ``MarketDataClient._raise_for_status`` lets exactly one 404 through: the
    one without an ``errmsg``. In CSV format the same answer arrives as a
    ``200`` whose body is a placeholder table, because the API drops the
    status when it renders it (MarketData-App/api#422, #89); that rule can go
    once the API answers ``404`` for CSV too.
    """
    if response.status_code == 404:
        return True
    if response.status_code not in VALID_STATUS_CODES or len(response.content) > 16:
        return False
    return [line for line in response.text.splitlines() if line] in _CSV_NO_DATA_BODIES


def column_key(name: str) -> str:
    """A column name the way the API matches it: case-insensitive and without
    spaces, so the human-readable ``Expiration Date`` equals the model's
    ``Expiration_Date``. The API's aliases (``open`` for ``o``, ``price``,
    ``date``) are endpoint-dependent and are not mirrored here."""
    return name.strip().lower().replace(" ", "").replace("_", "")


def parse_error(response: Response, reason: str) -> ParseError:
    """A ``ParseError`` for a body the API answered but the SDK cannot use."""
    return ParseError(
        f"Response body is not a valid answer of this resource ({reason}): "
        f"{resume_long_text(response.text, max_length=200)!r}",
        request=response.request,
        response=response,
    )


def format_timestamp(
    value: str | int | float | datetime.datetime | None,
) -> datetime.datetime:
    default_tz = pytz.timezone("US/Eastern")

    if isinstance(value, datetime.datetime):
        return value

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


def csv_header(columns: list[str]) -> str:
    """The header row of a CSV file, rendered by the same writer that renders
    a merged fan-out body, so an empty answer and a populated one quote and
    terminate their header identically."""
    output = StringIO()
    csv.writer(output).writerow(columns)
    return output.getvalue()


def merge_csv_responses(
    responses: list[Response], known_columns: list[str], *, with_header: bool = True
) -> str:
    """Merge the CSV bodies of a fan-out into one CSV text (#86).

    The header comes from the answers, never from the model: under
    ``columns=`` the API sends the requested columns only, and under
    ``use_human_readable`` their human-readable names. Every body must carry
    the same header, made of this resource's column names, and every row must
    be as wide as it; anything else (an HTML error page, a truncated body,
    a body the ``csv`` module cannot read, two symbols answering with
    different columns) raises ``ParseError`` naming the offending response. Headers are compared through ``column_key``,
    the same way they are validated, so two answers spelling the same column
    differently (case, a space after the comma) still merge; a different
    *order* is refused, because merging misaligned rows would corrupt the
    data. The file keeps the first answer's spelling. With ``with_header=False``
    (``add_headers=False``) the bodies carry no header, so only the row width
    is checked, against the first row seen.
    """
    known = {column_key(name) for name in known_columns}
    header: list[str] | None = None
    header_key: list[str] | None = None
    width: int | None = None
    rows_out: list[list[str]] = []

    for response in responses:
        try:
            rows = [row for row in csv.reader(StringIO(response.text)) if row]
        except csv.Error as exc:
            # A field past the reader's limit, or a NUL byte before Python
            # 3.11. `csv.Error` is not an SDK exception, and the body is not
            # this resource's answer either.
            raise parse_error(response, f"unreadable CSV: {exc}") from exc
        if with_header:
            if not rows:
                raise parse_error(response, "no header row")
            incoming, rows = rows[0], rows[1:]
            incoming[0] = incoming[0].lstrip("\ufeff")  # a BOM is not a column
            unknown = [name for name in incoming if column_key(name) not in known]
            if unknown:
                raise parse_error(response, f"unknown columns {unknown!r}")
            incoming_key = [column_key(name) for name in incoming]
            if header is None:
                header, header_key, width = incoming, incoming_key, len(incoming)
            elif incoming_key != header_key:
                raise parse_error(
                    response, f"header {incoming!r} differs from {header!r}"
                )
        for row in rows:
            if width is None:
                width = len(row)
            if len(row) != width:
                raise parse_error(response, f"row {row!r} does not have {width} values")
        rows_out.extend(rows)

    output = StringIO()
    writer = csv.writer(output)
    if header is not None:
        writer.writerow(header)
    writer.writerows(rows_out)
    return output.getvalue()


def json_answer_columns(
    responses: list[Response], answers: list[Any], keys: list[str]
) -> list[str]:
    """The columns a fan-out merges from its decoded JSON answers (#90).

    They are the ``keys`` (the model's columns) that any answer carries, keys
    the model does not know being left out. Since every answer must carry
    them all, a successful merge has the first answer's columns in the first
    answer's order: under ``columns=`` the API sends the requested columns
    only, in the order they were requested, which is also the order of the
    empty result and of every single-request resource. Every answer must be a
    JSON object
    carrying all of them as lists of one length, since the merge concatenates
    column by column and a missing or short column would shift every later
    row into the wrong symbol or chunk. Anything else raises ``ParseError``
    naming the offending response: a body that is not an object (``null``, a
    list), answers with none of the keys (a proxy's JSON error page), an
    answer missing a column another one carries, whichever it is, or a column
    that is not a list of the same length as the others. A merge with no
    columns would read as "no data" (#82).
    """
    for response, answer in zip(responses, answers, strict=True):
        if not isinstance(answer, dict):
            raise parse_error(response, "not a JSON object")
    known = set(keys)
    columns: list[str] = []
    for answer in answers:
        for key in answer:
            if key in known and key not in columns:
                columns.append(key)
    if not columns:
        raise parse_error(responses[0], "none of this resource's fields")
    for response, answer in zip(responses, answers):
        missing = [key for key in columns if key not in answer]
        if missing:
            raise parse_error(response, f"missing columns {missing!r}")
        not_lists = [key for key in columns if not isinstance(answer[key], list)]
        if not_lists:
            raise parse_error(response, f"columns {not_lists!r} are not lists")
        lengths = {key: len(answer[key]) for key in columns}
        if len(set(lengths.values())) > 1:
            raise parse_error(response, f"columns of different lengths {lengths!r}")
    return columns


_ONE_DAY = datetime.timedelta(days=1)


def _start_of_day(day: datetime.date, like: datetime.datetime) -> datetime.datetime:
    return datetime.datetime.combine(day, datetime.time.min, tzinfo=like.tzinfo)


def dict_to_csv(data: dict, exclude_keys: list[str] | None = None) -> str:
    """Render a decoded JSON object as CSV text.

    Column-oriented payloads (values are lists) become one row per entry;
    a flat object becomes a single row. Used for the endpoints that only
    speak JSON, so ``OutputFormat.CSV`` still produces a file.
    """
    if not data:
        return ""
    records = get_data_records(data, exclude_keys=exclude_keys)
    output = StringIO()
    # RFC 4180 line endings, the same the API uses for its own CSV; the file
    # writer stores the bytes verbatim on every platform.
    writer = csv.writer(output)
    if records:
        writer.writerow(list(records[0].keys()))
        writer.writerows(list(row.values()) for row in records)
    return output.getvalue()


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
