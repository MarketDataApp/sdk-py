import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class StockQuote:
    symbol: str
    ask: float
    askSize: int
    bid: float
    bidSize: int
    mid: float
    last: float
    change: float
    changepct: float
    volume: int
    updated: datetime.datetime

    def __post_init__(self):
        self.updated = format_timestamp(self.updated)

    @property
    def change_percent(self) -> float:
        return self.changepct

    def __repr__(self) -> str:
        result = f"Stock Quote:\n"
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
    Symbol: str
    Ask: float
    Ask_Size: int
    Bid: float
    Bid_Size: int
    Mid: float
    Last: float
    Change_Price: float
    Change_Percent: float
    Volume: int
    Date: datetime.datetime

    def __post_init__(self):
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        result = f"Stock Quote:\n"
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
        data["Change_Price"] = data["Change $"]
        data["Change_Percent"] = data["Change %"]
        data.pop("Change $")
        data.pop("Change %")

        data = {k.replace(" ", "_"): v for k, v in data.items()}

        return cls(**data)
