import pandas as pd
import pytz

from marketdata.input_types.base import DateFormat
from marketdata.output_handlers.base import BaseOutputHandler


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

    def _convert_timestamp_columns(
        self,
        df: pd.DataFrame,
        date_columns: list[str],
        date_format: DateFormat | None,
    ) -> pd.DataFrame:
        """Convert date/time columns to timezone-aware datetime objects."""
        convert_numeric = date_format != DateFormat.UNIX
        format_to_use = date_format or DateFormat.UNIX
        default_tz = pytz.timezone("US/Eastern")
        date_only_regex = r"^\d{4}-\d{2}-\d{2}$"

        for col in df.columns:
            if col not in date_columns:
                continue
            try:
                series = df[col]
                date_only_mask = series.astype("string").str.match(
                    date_only_regex, na=False
                )
                updated_series = None
                if date_only_mask.any():
                    date_only = pd.to_datetime(
                        series[date_only_mask], format="%Y-%m-%d", errors="coerce"
                    )
                    date_only = date_only.dt.tz_localize(default_tz)
                    updated_series = series.astype("object")
                    updated_series.loc[date_only_mask] = date_only

                if format_to_use == DateFormat.TIMESTAMP:
                    remaining = (
                        series[~date_only_mask] if date_only_mask.any() else series
                    )
                    parsed = pd.to_datetime(remaining, errors="coerce")
                    if parsed.dt.tz is None:
                        parsed = parsed.dt.tz_localize(default_tz)
                    else:
                        parsed = parsed.dt.tz_convert(default_tz)
                    parsed_mask = parsed.notna()
                    if parsed_mask.any():
                        if date_only_mask.any():
                            updated_series.loc[remaining.index[parsed_mask]] = parsed[
                                parsed_mask
                            ]
                        elif parsed_mask.all():
                            df[col] = parsed
                        else:
                            updated_series = series.astype("object")
                            updated_series.loc[remaining.index[parsed_mask]] = parsed[
                                parsed_mask
                            ]
                elif format_to_use == DateFormat.SPREADSHEET:
                    if convert_numeric:
                        remaining = (
                            series[~date_only_mask] if date_only_mask.any() else series
                        )
                        numeric = pd.to_numeric(remaining, errors="coerce")
                        numeric_mask = numeric.notna()
                        if numeric_mask.any():
                            converted = pd.to_datetime(
                                numeric[numeric_mask],
                                unit="D",
                                origin="1899-12-30",
                                utc=True,
                            ).dt.tz_convert(default_tz)
                            if date_only_mask.any():
                                updated_series.loc[remaining.index[numeric_mask]] = (
                                    converted
                                )
                            elif numeric_mask.all():
                                full_converted = pd.to_datetime(
                                    numeric,
                                    unit="D",
                                    origin="1899-12-30",
                                    utc=True,
                                ).dt.tz_convert(default_tz)
                                df[col] = full_converted
                            else:
                                updated_series = series.astype("object")
                                updated_series.loc[remaining.index[numeric_mask]] = (
                                    converted
                                )
                else:
                    if convert_numeric:
                        remaining = (
                            series[~date_only_mask] if date_only_mask.any() else series
                        )
                        numeric = pd.to_numeric(remaining, errors="coerce")
                        numeric_mask = numeric.notna()
                        if numeric_mask.any():
                            converted = pd.to_datetime(
                                numeric[numeric_mask], unit="s", utc=True
                            ).dt.tz_convert(default_tz)
                            if date_only_mask.any():
                                updated_series.loc[remaining.index[numeric_mask]] = (
                                    converted
                                )
                            elif numeric_mask.all():
                                full_converted = pd.to_datetime(
                                    numeric, unit="s", utc=True
                                ).dt.tz_convert(default_tz)
                                df[col] = full_converted
                            else:
                                updated_series = series.astype("object")
                                updated_series.loc[remaining.index[numeric_mask]] = (
                                    converted
                                )
                if updated_series is not None:
                    df[col] = updated_series
            except (ValueError, TypeError, AttributeError):
                pass

        return df

    def _validate_result(self, result: pd.DataFrame, **kwargs) -> pd.DataFrame:
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
