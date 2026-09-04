from importlib.metadata import version
from logging import DEBUG, INFO, Logger

from httpx import Client, Request, Response, TransportError

from marketdata.exceptions import (
    AuthenticationError,
    BadRequestError,
    ForbiddenError,
    MarketdataHttpError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from marketdata.input_types.base import UserUniversalAPIParams
from marketdata.internal_settings import (
    HTTP_TIMEOUT,
    MAX_RETRY_ATTEMPTS,
    NO_TOKEN_VALUE,
)
from marketdata.logger import get_logger
from marketdata.resources.funds import FundsResource
from marketdata.resources.markets import MarketsResource
from marketdata.resources.options import OptionsResource
from marketdata.resources.stocks import StocksResource
from marketdata.resources.utilities import UtilitiesResource
from marketdata.retry import parse_retry_after
from marketdata.settings import settings
from marketdata.types import UserRateLimits
from marketdata.utils import format_duration_log, obfuscate_token, resume_long_text


class MarketDataClient:

    def __init__(
        self,
        token: str = None,
        logger: Logger = None,
        max_retries: int = MAX_RETRY_ATTEMPTS,
    ):
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.token = token or settings.marketdata_token
        self.max_retries = max_retries
        self.library_version = version("marketdata-sdk-py")
        self.library_user_agent = self._get_user_agent()

        self.logger = logger or get_logger()
        self.logger.info(f"Initializing MarketDataClient")
        logged_token = (
            self.token if self.token == NO_TOKEN_VALUE else obfuscate_token(self.token)
        )
        self.logger.debug(f"Token: {logged_token}")
        self.logger.debug(f"Base URL: {settings.marketdata_base_url}")
        self.logger.debug(f"API Version: {settings.marketdata_api_version}")

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
        self.utilities = UtilitiesResource(client=self)

    def __del__(self):
        if hasattr(self, "client"):
            self.client.close()

    def _get_user_agent(self) -> str:
        return f"marketdata-sdk-py/{self.library_version}"

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

    @staticmethod
    def _error_message(response: Response) -> tuple[str, bool]:
        """The API's ``errmsg`` when the body carries one, else the raw body.

        Bounded so a malformed or hostile response cannot balloon exception
        messages and log output. The flag says whether an ``errmsg`` was found,
        which is what separates "invalid question" from "empty answer" on 404.
        """
        try:
            errmsg = response.json()["errmsg"]
            has_errmsg = True
        except Exception:
            errmsg = response.text
            has_errmsg = False
        return resume_long_text(str(errmsg), max_length=500), has_errmsg

    def _raise_for_status(self, response: Response) -> None:
        """Map the HTTP status to the exception taxonomy (SDK requirements §9.1).

        Returns normally for success and for a 404 without ``errmsg``: that is
        the API's "no data" answer to a valid question, and the resource
        renders an empty result for it.
        """
        status = response.status_code
        if status < 400:
            return

        message, has_errmsg = self._error_message(response)
        context = dict(request=response.request, response=response)

        if status == 400:
            raise BadRequestError(message, **context)
        if status == 401:
            raise AuthenticationError(message, **context)
        if status == 403:
            raise ForbiddenError(message, **context)
        if status == 404:
            if has_errmsg:
                raise NotFoundError(message, **context)
            return
        if status == 429:
            raise RateLimitError(
                message,
                response=response,
                retry_after=parse_retry_after(response.headers.get("Retry-After")),
            )
        if status >= 500:
            raise ServerError(message, **context)
        raise MarketdataHttpError(message, **context)

    def _setup_rate_limits(self):
        if self.token is NO_TOKEN_VALUE:
            return
        self.logger.debug("Setting up rate limits")
        self._make_request(
            method="GET",
            url="user/",
            check_rate_limits=False,
            include_api_version=False,
            populate_rate_limits=True,
            response_log_level=DEBUG,
        )

    def _extract_rate_limits(self, response: Response) -> UserRateLimits | None:
        self.logger.debug(f"Extracting response rate limits from response headers")
        try:
            return UserRateLimits(
                requests_limit=int(response.headers["x-api-ratelimit-limit"]),
                requests_remaining=int(response.headers["x-api-ratelimit-remaining"]),
                requests_reset=int(response.headers["x-api-ratelimit-reset"]),
                requests_consumed=int(response.headers["x-api-ratelimit-consumed"]),
            )
        except (KeyError, ValueError) as e:
            # Malformed response (e.g. missing or non-numeric rate-limit
            # headers) must not crash the request that already succeeded.
            self.logger.warning(
                f"Could not extract rate limits from response headers: {e!r}"
            )
            return None

    def _request_of(self, exc: TransportError, method: str, url: str) -> Request:
        # httpx attaches the request to the transport error; when it did not,
        # rebuild it so the support context still names the URL that failed.
        try:
            return exc.request
        except RuntimeError:  # pragma: no cover - httpx always sets it on send
            return Request(method, self.client.base_url.join(url))

    def _pre_request_logs(self, method: str, url: str, **kwargs):
        self.logger.debug(f"Making request to URL: {self.base_url}/{url}")

    def _post_request_logs(self, response: Response, response_log_level: int = INFO):
        cf_request_id = response.headers.get("cf-ray")
        duration = format_duration_log(response.elapsed.total_seconds() * 1000)
        method = response.request.method
        status = response.status_code
        url = response.request.url
        message = f"{method} {status} {duration} {cf_request_id} {url}"
        self.logger.log(response_log_level, message)

    def _make_request(
        self,
        method: str,
        url: str,
        check_rate_limits: bool = True,
        populate_rate_limits: bool = True,
        include_api_version: bool = True,
        timeout: int = HTTP_TIMEOUT,
        response_log_level: int = INFO,
        **kwargs,
    ) -> Response:
        if self.token is NO_TOKEN_VALUE:
            check_rate_limits = False

        self._check_rate_limits(raise_error=check_rate_limits)

        if include_api_version:
            url = f"{self.api_version}/{url}"

        self._pre_request_logs(method, url, **kwargs)
        try:
            response = self.client.request(method, url, **kwargs, timeout=timeout)
        except TransportError as exc:
            # Connection failures and timeouts never got an answer: NetworkError
            # (retried by the resource's retry loop).
            raise NetworkError(
                f"{type(exc).__name__}: {exc}",
                request=self._request_of(exc, method, url),
            ) from exc
        self._post_request_logs(response, response_log_level)

        self._raise_for_status(response)

        if populate_rate_limits:
            rate_limits = self._extract_rate_limits(response)
            if rate_limits is not None:
                self.rate_limits = rate_limits

        return response
