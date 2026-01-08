import datetime
from enum import Enum
from typing import TYPE_CHECKING

from marketdata.exceptions import BadStatusCodeError, InvalidStatusDataError
from marketdata.internal_settings import REFRESH_API_STATUS_INTERVAL

if TYPE_CHECKING:
    from marketdata.client import MarketDataClient


class APIStatusResult(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class APIStatusData:
    def __init__(self):
        self.service = []
        self.status = []
        self.online = []
        self.uptimePct30d = []
        self.uptimePct90d = []
        self.updated = []

    def update(self, data: dict):
        try:
            self.service = data["service"]
            self.status = data["status"]
            self.online = data["online"]
            self.uptimePct30d = data["uptimePct30d"]
            self.uptimePct90d = data["uptimePct90d"]
            self.updated = data["updated"]
        except KeyError as e:
            raise InvalidStatusDataError(f"Invalid status data: {e}") from e

    @property
    def last_updated(self) -> datetime.datetime:
        if not self.updated:
            return datetime.datetime(1970, 1, 1)
        return datetime.datetime.fromtimestamp(min(self.updated))

    @property
    def should_refresh(self) -> bool:
        return datetime.datetime.now() - self.last_updated > REFRESH_API_STATUS_INTERVAL

    def get_api_status(
        self, client: "MarketDataClient", service: str
    ) -> APIStatusResult:
        client.logger.debug(f"Checking if service {service} is online")
        if self.should_refresh and not self.refresh(client):
            return APIStatusResult.UNKNOWN

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
            )
            data = response.json()
            self.update(data)
            return True
        except (BadStatusCodeError, InvalidStatusDataError) as e:
            client.logger.error(f"Failed to refresh API status: {e}")
            return False


API_STATUS_DATA = APIStatusData()
