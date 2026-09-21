import polars as pl
import pytz

from marketdata.input_types.base import DateFormat
from marketdata.output_handlers.base import BaseOutputHandler

_DTYPES = {float: pl.Float64, int: pl.Int64, bool: pl.Boolean, str: pl.String}


class PolarsOutputHandler(BaseOutputHandler):
    def _normalize_value(self, value, max_length):
        if isinstance(value, (list, tuple)):
            padded = list(value) + [None] * (max_length - len(value))
            return pl.Series(padded, strict=False)
        else:
            return pl.Series([value] * max_length, strict=False)

    def _initialize_dataframe(self) -> pl.DataFrame:
        try:
            return pl.DataFrame(self.data)
        except Exception:
            try:
                lengths = [
                    len(v) for v in self.data.values() if isinstance(v, (list, tuple))
                ]
                max_length = max(lengths) if lengths else 1
                return pl.DataFrame(
                    {
                        k: self._normalize_value(v, max_length)
                        for k, v in self.data.items()
                    },
                    strict=False,
                )
            except Exception as e:
                raise ValueError(f"Failed to initialize dataframe: {e}") from e

    def _convert_timestamp_columns(
        self,
        df: pl.DataFrame,
        date_columns: list[str],
        date_format: DateFormat | None,
    ) -> pl.DataFrame:
        """Convert date/time columns to timezone-aware datetime objects."""
        if date_format == DateFormat.UNIX:
            return df

        format_to_use = date_format or DateFormat.UNIX
        default_tz = pytz.timezone("US/Eastern").zone

        for col in df.columns:
            if col not in date_columns:
                continue
            try:
                if format_to_use == DateFormat.TIMESTAMP:
                    cleaned = pl.col(col).str.replace(
                        r"(Z|[+-]\d{2}:?\d{2})$", "", literal=False
                    )
                    df = df.with_columns(
                        cleaned.str.strptime(pl.Datetime, strict=False)
                        .dt.replace_time_zone("UTC")
                        .dt.convert_time_zone(default_tz)
                        .alias(col)
                    )
                elif format_to_use == DateFormat.SPREADSHEET:
                    df = df.with_columns(
                        pl.from_epoch(
                            ((pl.col(col).cast(pl.Float64) - 25569) * 86400).cast(
                                pl.Int64
                            ),
                            time_unit="s",
                        )
                        .dt.replace_time_zone("UTC")
                        .dt.convert_time_zone(default_tz)
                        .alias(col)
                    )
                else:
                    df = df.with_columns(
                        pl.from_epoch(pl.col(col), time_unit="s")
                        .dt.replace_time_zone("UTC")
                        .dt.convert_time_zone(default_tz)
                        .alias(col)
                    )
            except (ValueError, TypeError, AttributeError, pl.exceptions.PolarsError):
                pass

        return df

    def _cast_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        """Give each column the dtype of its annotation where no value changes.

        A column of nulls takes the dtype outright, whole numbers in a float
        column become floats and narrower numbers are widened to 64 bits.

        Args:
            df: The result, before its date columns are converted.

        Returns:
            The same frame with its columns cast.
        """
        casts = []
        for column, kind in self._column_kinds().items():
            if column not in df.columns:
                continue
            dtype, target = df.schema[column], _DTYPES[kind]
            widen = (kind is float and dtype.is_numeric()) or (
                kind is int and dtype.is_integer()
            )
            if dtype != target and (dtype == pl.Null or widen):
                casts.append(pl.col(column).cast(target))
        return df.with_columns(casts) if casts else df

    def _validate_result(self, result: pl.DataFrame, **kwargs) -> pl.DataFrame:
        """Order and type the result.

        Args:
            result: The frame built from the answer.
            **kwargs: ``date_columns`` to convert besides the model's.

        Returns:
            The frame in model order, with its columns cast and its dates
            converted.
        """
        result = result.select(self._column_order(result.columns))
        result = self._cast_columns(result)
        date_columns = self._get_date_columns() + self._get_datetime_columns()
        date_columns.extend(kwargs.get("date_columns", []))
        date_format = self.user_universal_params.date_format
        return self._convert_timestamp_columns(result, date_columns, date_format)

    def _get_result(self, *args, **kwargs) -> pl.DataFrame:
        self.data.pop("s", None)
        df = self._initialize_dataframe()
        return df
