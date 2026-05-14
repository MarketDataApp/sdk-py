import datetime
import logging
import threading
from enum import Enum
from typing import TYPE_CHECKING

from marketdata.exceptions import BadStatusCodeError, InvalidStatusDataError
from marketdata.internal_settings import (
    CACHE_VALIDITY_INTERVAL,
    REFRESH_API_STATUS_INTERVAL,
)

if TYPE_CHECKING:
    from marketdata.client import MarketDataClient


class APIStatusResult(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class APIStatusData:
    def __init__(self):
        self._lock = threading.Lock()
        self._refresh_in_flight = False
        self._refresh_thread: threading.Thread | None = None
        self._last_refresh_at: datetime.datetime | None = None
        self.service = []
        self.status = []
        self.online = []
        self.uptimePct30d = []
        self.uptimePct90d = []
        self.updated = []

    def update(self, data: dict):
        try:
            new_service = data["service"]
            new_status = data["status"]
            new_online = data["online"]
            new_uptime30 = data["uptimePct30d"]
            new_uptime90 = data["uptimePct90d"]
            new_updated = data["updated"]
        except KeyError as e:
            raise InvalidStatusDataError(f"Invalid status data: {e}") from e
        with self._lock:
            self.service = new_service
            self.status = new_status
            self.online = new_online
            self.uptimePct30d = new_uptime30
            self.uptimePct90d = new_uptime90
            self.updated = new_updated
            self._last_refresh_at = datetime.datetime.now()

    @property
    def last_updated(self) -> datetime.datetime:
        if not self.updated:
            return datetime.datetime(1970, 1, 1)
        return datetime.datetime.fromtimestamp(min(self.updated))

    @property
    def cache_age(self) -> datetime.timedelta:
        if self._last_refresh_at is None:
            return datetime.timedelta.max
        return datetime.datetime.now() - self._last_refresh_at

    @property
    def should_refresh(self) -> bool:
        return self.cache_age >= REFRESH_API_STATUS_INTERVAL

    @property
    def is_cache_stale(self) -> bool:
        return self.cache_age >= CACHE_VALIDITY_INTERVAL

    def get_api_status(
        self, client: "MarketDataClient", service: str
    ) -> APIStatusResult:
        client.logger.debug(f"Checking if service {service} is online")

        if self.is_cache_stale:
            self._trigger_async_refresh(client)
            return APIStatusResult.UNKNOWN

        if self.should_refresh:
            self._trigger_async_refresh(client)

        with self._lock:
            if service not in self.service:
                client.logger.error(f"Service {service} not found in API status")
                return APIStatusResult.UNKNOWN

            service_index = self.service.index(service)
            if self.status[service_index] != APIStatusResult.ONLINE:
                client.logger.error(f"Service {service} is offline")
                return APIStatusResult.OFFLINE
            if not self.online[service_index]:
                client.logger.error(f"Service {service} is not online")
                return APIStatusResult.OFFLINE
            client.logger.debug(f"Service {service} is online")
            return APIStatusResult.ONLINE

    def refresh(self, client: "MarketDataClient") -> bool:
        try:
            url = "/status/"
            client.logger.debug(f"Refreshing API status from url: {url}")
            response = client._make_request(
                method="GET",
                url=url,
                check_rate_limits=False,
                include_api_version=False,
                populate_rate_limits=False,
                response_log_level=logging.DEBUG,
            )
            data = response.json()
            self.update(data)
            return True
        except (BadStatusCodeError, InvalidStatusDataError) as e:
            client.logger.error(f"Failed to refresh API status: {e}")
            return False

    def _trigger_async_refresh(self, client: "MarketDataClient") -> None:
        with self._lock:
            if self._refresh_in_flight:
                return
            self._refresh_in_flight = True

        thread = threading.Thread(
            target=self._async_refresh, args=(client,), daemon=True
        )
        self._refresh_thread = thread
        thread.start()

    def _async_refresh(self, client: "MarketDataClient") -> None:
        try:
            self.refresh(client)
        finally:
            with self._lock:
                self._refresh_in_flight = False


API_STATUS_DATA = APIStatusData()
