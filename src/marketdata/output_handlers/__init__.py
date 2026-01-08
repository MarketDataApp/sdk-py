from functools import lru_cache

from marketdata.internal_settings import DATAFRAME_HANDLERS_PRIORITY
from marketdata.output_handlers.base import BaseOutputHandler


@lru_cache(maxsize=1)
def _try_get_handler(handler: str) -> BaseOutputHandler:
    handler_class = None

    try:
        if handler == "pandas":
            from marketdata.output_handlers.pandas import PandasOutputHandler

            handler_class = PandasOutputHandler

        elif handler == "polars":
            from marketdata.output_handlers.polars import PolarsOutputHandler

            handler_class = PolarsOutputHandler

    # This is a fallback for when the library is not installed, will never be reached in tests.
    except ImportError:  # pragma: no cover
        pass

    return handler_class


def get_dataframe_output_handler() -> BaseOutputHandler:
    for handler in DATAFRAME_HANDLERS_PRIORITY:
        handler = _try_get_handler(handler)
        if handler is not None:
            return handler
    raise ValueError("No dataframe output handler found")
