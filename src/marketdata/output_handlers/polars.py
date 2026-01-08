import polars as pl

from marketdata.output_handlers.base import BaseOutputHandler


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

    def get_result(self, *args, **kwargs) -> pl.DataFrame:
        self.data.pop("s", None)
        df = self._initialize_dataframe()
        return df
