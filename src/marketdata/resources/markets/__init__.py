from marketdata.resources.base import BaseResource
from marketdata.resources.markets.status import status


class MarketsResource(BaseResource):
    status = status


__all__ = ["MarketsResource"]
