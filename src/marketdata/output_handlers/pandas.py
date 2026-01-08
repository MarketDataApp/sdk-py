import pandas as pd

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
        except Exception as e:
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

    def get_result(self, *args, **kwargs) -> pd.DataFrame:
        index_columns = kwargs.get("index_columns", [])
        df = self._initialize_dataframe()
        df = self._validate_dataframe(df)

        for column in index_columns:
            if column in df.columns:
                df.set_index(column, inplace=True)

        return df
