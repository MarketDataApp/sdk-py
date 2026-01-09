import polars as pl
import pytz

from marketdata.input_types.base import DateFormat
from marketdata.output_handlers.base import BaseOutputHandler, TIMESTAMP_COLUMN_NAMES


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

    def _is_timestamp_column(self, col_name: str) -> bool:
        """Check if a column is likely a timestamp column by column name."""
        return col_name.lower() in TIMESTAMP_COLUMN_NAMES

    def _convert_timestamp_columns(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert Unix timestamp columns to timezone-aware datetime objects."""
        # Only skip conversion if date_format is explicitly set to UNIX
        # If date_format is None (not specified), apply conversion (default behavior)
        if self.date_format is not None and self.date_format == DateFormat.UNIX:
            return df

        # Default timezone for US markets (NYSE/NASDAQ)
        default_tz = pytz.timezone('US/Eastern').zone

        for col in df.columns:
            if self._is_timestamp_column(col):
                try:
                    # Convert from Unix timestamp (seconds) to datetime
                    # First convert to UTC, then convert to exchange timezone
                    df = df.with_columns(
                        pl.from_epoch(pl.col(col), time_unit="s")
                        .dt.replace_time_zone("UTC")
                        .dt.convert_time_zone(default_tz)
                        .alias(col)
                    )
                except Exception:
                    # If conversion fails, leave the column as-is
                    pass

        return df

    def get_result(self, *args, **kwargs) -> pl.DataFrame:
        self.data.pop("s", None)
        df = self._initialize_dataframe()
        df = self._convert_timestamp_columns(df)
        return df
