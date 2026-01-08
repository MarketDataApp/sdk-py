import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class StockPrice:
    s: str
    symbol: str
    mid: float
    change: float
    changepct: float
    updated: datetime.datetime

    def __post_init__(self):
        self.updated = format_timestamp(self.updated)

    def __repr__(self) -> str:
        result = f"Stock Price:\n"
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
    Symbol: str
    Mid: float
    Change_Price: float
    Change_Percent: float
    Date: datetime.datetime

    def __post_init__(self):
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        result = f"Stock Prices:\n"
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
        data["Change_Price"] = data["Change $"]
        data["Change_Percent"] = data["Change %"]
        data.pop("Change $")
        data.pop("Change %")
        return cls(**data)
