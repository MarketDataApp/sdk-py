import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from marketdata.output_types.columns import to_fields
from marketdata.output_types.money import coerce_numbers
from marketdata.utils import format_timestamp


@dataclass
class StockPrice:
    s: str
    symbol: str
    mid: Decimal
    change: Decimal
    changepct: float
    updated: datetime.datetime

    def __post_init__(self):
        coerce_numbers(self)
        self.updated = format_timestamp(self.updated)

    def __repr__(self) -> str:
        result = "Stock Price:\n"
        result += f"Symbol: {self.symbol}\n"
        result += f"Price: {self.mid}\n"
        result += f"Change: {self.change}\n"
        result += f"Change Percent: {self.changepct}\n"
        result += f"Updated: {self.updated.isoformat()}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_dict(cls, data: dict) -> "StockPrice":
        return cls(**data)


@dataclass
class StockPricesHumanReadable:
    api_model: ClassVar[type] = StockPrice
    api_names: ClassVar[dict[str, str]] = {
        "Change_Price": "Change $",
        "Change_Percent": "Change %",
    }

    Symbol: str
    Mid: Decimal
    Change_Price: Decimal
    Change_Percent: float
    Date: datetime.datetime

    def __post_init__(self):
        coerce_numbers(self)
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        result = "Stock Prices:\n"
        result += f"Symbol: {self.Symbol}\n"
        result += f"Price: {self.Mid}\n"
        result += f"Change Price: {self.Change_Price}\n"
        result += f"Change Percent: {self.Change_Percent}\n"
        result += f"Date: {self.Date.isoformat()}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_dict(cls, data: dict) -> "StockPricesHumanReadable":
        """Build the model from an API answer keyed by column name."""
        return cls(**to_fields(cls, data))
