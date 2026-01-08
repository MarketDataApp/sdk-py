from marketdata.resources.base import BaseResource
from marketdata.resources.funds.candles import candles


class FundsResource(BaseResource):
    candles = candles


__all__ = ["FundsResource"]
