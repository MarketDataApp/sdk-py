from importlib.metadata import version
from logging import Logger
from typing import Callable

from httpx import Client, HTTPStatusError, Response

from marketdata.exceptions import BadStatusCodeError, RateLimitError, RequestError
from marketdata.input_types.base import UserUniversalAPIParams
from marketdata.internal_settings import (
    HTTP_TIMEOUT,
    NO_TOKEN_VALUE,
    RETRY_STATUS_CODES,
)
from marketdata.logger import get_logger
from marketdata.resources.funds import FundsResource
from marketdata.resources.markets import MarketsResource
from marketdata.resources.options import OptionsResource
from marketdata.resources.stocks import StocksResource
from marketdata.settings import settings
from marketdata.types import UserRateLimits


class MarketDataClient:

    def __init__(self, token: str = None, logger: Logger = None):
        self.token = token or settings.marketdata_token
        self.library_version = version("marketdata-sdk-py")
        self.library_user_agent = self._get_user_agent()

        self.logger = logger or get_logger()
        self.logger.info(f"Initializing MarketDataClient")
        self.logger.debug(f"Token: {self.token}")
        self.logger.info(f"Base URL: {settings.marketdata_base_url}")
        self.logger.info(f"API Version: {settings.marketdata_api_version}")

        self.base_url = settings.marketdata_base_url
        self.api_version = settings.marketdata_api_version
        self.headers = self._get_headers()
        self.client = self._get_client()
        self.default_params = UserUniversalAPIParams()

        # Set initial rate limits
        self.rate_limits = None
        self._setup_rate_limits()

        # Set resources
        self.funds = FundsResource(client=self)
        self.markets = MarketsResource(client=self)
        self.options = OptionsResource(client=self)
        self.stocks = StocksResource(client=self)

    def __del__(self):
        if hasattr(self, "client"):
            self.client.close()

    def _get_user_agent(self) -> str:
        return f"marketdata-py-{self.library_version}"

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": self.library_user_agent,
        }
        if self.token is NO_TOKEN_VALUE:
            headers.pop("Authorization")
            self.logger.warning("No token provided, starting in demo mode")
        return headers

    def _get_client(self) -> Client:
        return Client(
            base_url=settings.marketdata_base_url,
            headers=self.headers,
        )

    def _check_rate_limits(self, raise_error: bool = True):
        if raise_error and self.rate_limits is None:
            self.logger.error("Rate limits cant be checked")
            raise RateLimitError("Rate limits cant be checked")

        if raise_error and self.rate_limits.requests_remaining <= 0:
            raise RateLimitError("Rate limit exceeded")

    def _validate_response_status_code(
        self,
        response: Response,
        retry_status_codes: list[int] | int | Callable,
        raise_for_status: bool,
    ) -> None:
        def _get_response_errmsg(response: Response):
            try:
                data = response.json()
                return data["errmsg"]
            except:
                return response.text

        def _validate_status(response: Response):
            try:
                response.raise_for_status()
            except HTTPStatusError:
                return False
            return True

        conditions_to_error: list[tuple[bool, str]] = [
            (
                retry_status_codes
                and isinstance(retry_status_codes, int)
                and retry_status_codes == response.status_code,
                RequestError(f"Request failed with: {_get_response_errmsg(response)}"),
            ),
            (
                retry_status_codes
                and isinstance(retry_status_codes, Callable)
                and retry_status_codes(response.status_code),
                RequestError(f"Request failed with: {_get_response_errmsg(response)}"),
            ),
            (
                retry_status_codes
                and isinstance(retry_status_codes, list)
                and response.status_code in retry_status_codes,
                RequestError(f"Request failed with: {_get_response_errmsg(response)}"),
            ),
            (
                raise_for_status and not _validate_status(response),
                BadStatusCodeError(_get_response_errmsg(response)),
            ),
        ]
        for condition, exc in conditions_to_error:
            if condition:
                raise exc

    def _setup_rate_limits(self):
        if self.token is NO_TOKEN_VALUE:
            return
        self.logger.debug("Setting up rate limits")
        self._make_request(
            method="GET",
            url="/user/",
            check_rate_limits=False,
            include_api_version=False,
            populate_rate_limits=True,
        )

    def _extract_rate_limits(self, response: Response) -> UserRateLimits:
        self.logger.debug(f"Extracting response rate limits from response headers")
        return UserRateLimits(
            requests_limit=int(response.headers["x-api-ratelimit-limit"]),
            requests_remaining=int(response.headers["x-api-ratelimit-remaining"]),
            requests_reset=int(response.headers["x-api-ratelimit-reset"]),
            requests_consumed=int(response.headers["x-api-ratelimit-consumed"]),
        )

    def _make_request(
        self,
        method: str,
        url: str,
        check_rate_limits: bool = True,
        populate_rate_limits: bool = True,
        include_api_version: bool = True,
        timeout: int = HTTP_TIMEOUT,
        retry_status_codes: list[int] = RETRY_STATUS_CODES,
        raise_for_status: bool = True,
        **kwargs,
    ) -> Response:
        if self.token is NO_TOKEN_VALUE:
            check_rate_limits = False

        self._check_rate_limits(raise_error=check_rate_limits)

        if include_api_version:
            url = f"{self.api_version}/{url}"

        response = self.client.request(method, url, **kwargs, timeout=timeout)

        self._validate_response_status_code(
            response, retry_status_codes, raise_for_status
        )

        if populate_rate_limits:
            self.rate_limits = self._extract_rate_limits(response)

        return response
