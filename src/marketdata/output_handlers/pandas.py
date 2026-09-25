import numpy as np
import pandas as pd
import pytz

from marketdata.input_types.base import DateFormat
from marketdata.output_handlers.base import BaseOutputHandler

_DTYPES = {float: "float64", int: "int64", bool: "bool", str: "object"}


class PandasOutputHandler(BaseOutputHandler):
    def _try_get_plain_dataframe(self) -> pd.DataFrame:
        try:
            df = pd.DataFrame(self.data)
        except Exception:
            return None
        return df

    def _try_get_normalized_dataframe(self) -> pd.DataFrame:
        try:
            list_lengths = [len(v) for v in self.data.values() if isinstance(v, list)]
            max_length = max(list_lengths) if list_lengths else 1

            def _get_value(value):
                if isinstance(value, list):
                    return pd.Series(value)
                return [value] * max_length

            df = pd.DataFrame({k: _get_value(v) for k, v in self.data.items()})
        except Exception:
            return None
        return df

    def _initialize_dataframe(self) -> pd.DataFrame:
        df = self._try_get_plain_dataframe()
        if df is None:
            df = self._try_get_normalized_dataframe()
        if df is None:
            raise ValueError("Failed to initialize dataframe")
        return df

    def _validate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if "s" in df.columns:
            df.drop("s", axis=1, inplace=True)
        return df

    def _convert_timestamp_columns(
        self,
        df: pd.DataFrame,
        date_columns: list[str],
        date_format: DateFormat | None,
    ) -> pd.DataFrame:
        """Convert the date columns to US/Eastern datetimes.

        Args:
            df: The result, with its columns cast.
            date_columns: The columns to convert.
            date_format: The request's date format. ``None`` reads the values
                as Unix seconds, and ``DateFormat.UNIX`` leaves them as numbers.

        Returns:
            The same frame. A column that cannot be converted keeps its values.
        """
        if date_format == DateFormat.UNIX:
            return df

        format_to_use = date_format or DateFormat.UNIX
        default_tz = pytz.timezone("US/Eastern")

        for col in df.columns:
            if col not in date_columns:
                continue
            try:
                if format_to_use == DateFormat.TIMESTAMP:
                    df[col] = _from_timestamp_text(df[col], default_tz)
                elif format_to_use == DateFormat.SPREADSHEET:
                    df[col] = _from_serial(df[col], default_tz)
                else:
                    df[col] = _from_seconds(df[col], utc=True).dt.tz_convert(default_tz)
            except (ValueError, TypeError, AttributeError):
                pass

        return df

    def _cast_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Give each column the dtype of its annotation where no value changes.

        An empty column takes the dtype outright, an all-null number column
        becomes ``float64`` and whole numbers in a float column become floats.
        pandas holds no null in an ``int64`` or ``bool`` column, so a column
        with nulls keeps the dtype its values give it.

        Args:
            df: The result, before its date columns are converted.

        Returns:
            The same frame with its columns cast.
        """
        for column, kind in self._column_kinds().items():
            if column not in df.columns:
                continue
            values = df[column]
            if values.empty:
                df[column] = values.astype(_DTYPES[kind])
            elif kind in (float, int) and values.isna().all():
                df[column] = values.astype("float64")
            elif kind is float and pd.api.types.is_integer_dtype(values):
                df[column] = values.astype("float64")
        return df

    def _validate_result(self, result: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """Order, type and index the result.

        Args:
            result: The frame built from the answer.
            **kwargs: ``date_columns`` to convert besides the model's, and
                ``index_columns`` to index by when present.

        Returns:
            The frame in model order, with its columns cast, its dates
            converted and its index set.
        """
        result = result.reindex(columns=self._column_order(list(result.columns)))
        result = self._cast_columns(result)
        date_columns = self._get_date_columns() + self._get_datetime_columns()
        manual_date_columns = kwargs.get("date_columns", [])
        date_columns.extend(manual_date_columns)

        index_columns = kwargs.get("index_columns", [])
        date_format = self.user_universal_params.date_format

        result = self._convert_timestamp_columns(result, date_columns, date_format)

        for column in index_columns:
            if column in result.columns:
                result.set_index(column, inplace=True)

        return result

    def _get_result(self, *args, **kwargs) -> pd.DataFrame:
        df = self._initialize_dataframe()
        df = self._validate_dataframe(df)
        return df


def _localize(wall: pd.Series, tz) -> pd.Series:
    """Read naive wall-clock datetimes as times in ``tz``.

    Args:
        wall: Naive datetimes.
        tz: The zone they are wall-clock times of.

    Returns:
        The datetimes in ``tz``. A time the clocks go through twice is the
        first one, a time they skip is ``NaT``.
    """
    return wall.dt.tz_localize(
        tz, ambiguous=np.ones(len(wall), dtype=bool), nonexistent="NaT"
    )


def _from_timestamp_text(values: pd.Series, tz) -> pd.Series:
    """Read the API's ``dateformat=timestamp`` strings.

    Args:
        values: Datetimes with their UTC offset (``2026-09-21 14:02:10 -04:00``)
            or dates (``2026-09-21``).
        tz: The zone to express them in, and the one a date is a day of.

    Returns:
        The datetimes in ``tz``; a date is its midnight there.

    Raises:
        ValueError: If a value is not a date or a datetime.
    """
    text = values.astype("string")
    is_date = text.str.fullmatch(r"\d{4}-\d{2}-\d{2}").fillna(False).astype(bool)
    moments = pd.to_datetime(text.where(~is_date), utc=True).dt.tz_convert(tz)
    dates = _localize(pd.to_datetime(text.where(is_date), format="%Y-%m-%d"), tz)
    return moments.where(~is_date, dates)


def _from_seconds(
    seconds: pd.Series, origin: str | pd.Timestamp = "unix", utc: bool = False
) -> pd.Series:
    """Read numbers of seconds as datetimes, and a null as ``NaT``.

    Args:
        seconds: Seconds since ``origin``.
        origin: What the seconds count from, as ``pd.to_datetime`` reads it.
        utc: Whether the datetimes are UTC rather than naive.

    Returns:
        The datetimes, ``NaT`` where ``seconds`` is null.

    Raises:
        ValueError: If a value is not a number, or is out of the datetime range.
    """
    missing = seconds.isna()
    # Nulls go in as 0 and come back as NaT: pandas 2.x can overflow on a null.
    converted = pd.to_datetime(
        seconds.mask(missing, 0), unit="s", origin=origin, utc=utc
    )
    return converted.mask(missing)


def _from_serial(values: pd.Series, tz) -> pd.Series:
    """Read the API's ``dateformat=spreadsheet`` serials.

    Args:
        values: Days since 1899-12-30 of a wall-clock time in ``tz``.
        tz: The zone of that wall clock.

    Returns:
        The datetimes in ``tz``, to the second.

    Raises:
        ValueError: If a value is not a number, or is out of the datetime range.
    """
    seconds = (pd.to_numeric(values) * 86400).round()
    return _localize(_from_seconds(seconds, origin=pd.Timestamp("1899-12-30")), tz)
