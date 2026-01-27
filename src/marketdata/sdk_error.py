from functools import wraps
from typing import Callable

from marketdata.exceptions import (
    BaseMarketdataException,
    MinMaxDateValidationError,
    RateLimitError,
)
from marketdata.resources.base import BaseResource


class MarketDataClientErrorResult:
    """Special result type for handling errors"""

    error: Exception

    def __init__(self, error: BaseMarketdataException):
        self.error = error

    @property
    def support_context(self) -> dict:
        return self.error.support_context

    @property
    def support_info(self) -> str:
        lines = ["--- MARKET DATA SUPPORT INFO ---"]
        for field, value in self.support_context.items():
            lines.append(f"{field}:\t\t{value}")
        lines.append("--------------------------------")
        return "\n".join(lines)

    def __repr__(self) -> str:
        data = self.support_context
        data_str = "\n".join([f"\t{k}={v}" for k, v in data.items()])
        return f"MarketDataClientErrorResult(\n{data_str}\n)"

    def __str__(self) -> str:
        return self.__repr__()


def handle_exceptions(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        resource: BaseResource = args[0]
        logger = resource.logger

        try:
            return func(*args, **kwargs)

        except RateLimitError as e:
            logger.error(f"Rate limit error: {e}")
            return MarketDataClientErrorResult(error=e)

        except MinMaxDateValidationError as e:
            logger.error(f"Validation error: {e}")
            return MarketDataClientErrorResult(error=e)

        except Exception as e:
            logger.error(f"Error: {e}")
            return MarketDataClientErrorResult(error=e)

    return wrapper
