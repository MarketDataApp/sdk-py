import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from marketdata.output_types.columns import _to_fields
from marketdata.output_types.money import coerce_numbers
from marketdata.utils import format_timestamp


@dataclass
class StockQuote:
    symbol: str
    ask: Decimal
    askSize: int
    bid: Decimal
    bidSize: int
    mid: Decimal
    last: Decimal
    change: Decimal
    changepct: float
    volume: int
    updated: datetime.datetime

    def __post_init__(self):
        coerce_numbers(self)
        self.updated = format_timestamp(self.updated)

    @property
    def change_percent(self) -> float:
        return self.changepct

    def __repr__(self) -> str:
        result = "Stock Quote:\n"
        result += f"Symbol: {self.symbol}\n"
        result += f"Ask: {self.ask}\n"
        result += f"Ask Size: {self.askSize}\n"
        result += f"Bid: {self.bid}\n"
        result += f"Bid Size: {self.bidSize}\n"
        result += f"Mid: {self.mid}\n"
        result += f"Last: {self.last}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_dict(cls, data: dict) -> "StockQuote":
        return cls(**data)


@dataclass
class StockQuotesHumanReadable:
    api_model: ClassVar[type] = StockQuote
    api_names: ClassVar[dict[str, str]] = {
        "Change_Price": "Change $",
        "Change_Percent": "Change %",
    }

    Symbol: str
    Ask: Decimal
    Ask_Size: int
    Bid: Decimal
    Bid_Size: int
    Mid: Decimal
    Last: Decimal
    Change_Price: Decimal
    Change_Percent: float
    Volume: int
    Date: datetime.datetime

    def __post_init__(self):
        coerce_numbers(self)
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        result = "Stock Quote:\n"
        result += f"Symbol: {self.Symbol}\n"
        result += f"Ask: {self.Ask}\n"
        result += f"Ask Size: {self.Ask_Size}\n"
        result += f"Bid: {self.Bid}\n"
        result += f"Bid Size: {self.Bid_Size}\n"
        result += f"Mid: {self.Mid}\n"
        result += f"Last: {self.Last}\n"
        result += f"Change Price: {self.Change_Price}\n"
        result += f"Change Percent: {self.Change_Percent}\n"
        result += f"Volume: {self.Volume}\n"
        result += f"Date: {self.Date.isoformat()}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_dict(cls, data: dict) -> "StockQuotesHumanReadable":
        """Build the model from an API answer keyed by column name."""
        return cls(**_to_fields(cls, data))
