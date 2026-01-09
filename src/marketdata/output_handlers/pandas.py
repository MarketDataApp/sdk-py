import pandas as pd
import pytz

from marketdata.input_types.base import DateFormat
from marketdata.output_handlers.base import BaseOutputHandler, TIMESTAMP_COLUMN_NAMES


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
            _get_value = lambda value: (
                pd.Series(value) if isinstance(value, list) else [value] * max_length
            )
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

    def _is_timestamp_column(self, col_name: str) -> bool:
        """Check if a column is likely a timestamp column by column name."""
        return col_name.lower() in TIMESTAMP_COLUMN_NAMES

    def _convert_timestamp_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert Unix timestamp columns to timezone-aware datetime objects."""
        # Only skip conversion if date_format is explicitly set to UNIX
        # If date_format is None (not specified), apply conversion (default behavior)
        if self.date_format is not None and self.date_format == DateFormat.UNIX:
            return df

        # Default timezone for US markets (NYSE/NASDAQ)
        default_tz = pytz.timezone('US/Eastern')

        for col in df.columns:
            if self._is_timestamp_column(col):
                try:
                    # Convert to UTC first, then to exchange timezone
                    df[col] = pd.to_datetime(df[col], unit='s', utc=True).dt.tz_convert(default_tz)
                except Exception:
                    # If conversion fails, leave the column as-is
                    pass

        return df

    def get_result(self, *args, **kwargs) -> pd.DataFrame:
        index_columns = kwargs.get("index_columns", [])
        df = self._initialize_dataframe()
        df = self._validate_dataframe(df)
        df = self._convert_timestamp_columns(df)

        for column in index_columns:
            if column in df.columns:
                df.set_index(column, inplace=True)

        return df
