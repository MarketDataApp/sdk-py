from functools import wraps
from typing import Callable

from marketdata.exceptions import MinMaxDateValidationError, RateLimitError
from marketdata.resources.base import BaseResource


class MarketDataClientErrorResult:
    """Special result type for handling errors"""

    error: Exception

    def __init__(self, error: Exception):
        self.error = error

    def __repr__(self) -> str:
        error_name = self.error.__class__.__name__
        error_message = str(self.error)
        return (
            f"MarketDataClientErrorResult(error={error_name}, message={error_message})"
        )

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
