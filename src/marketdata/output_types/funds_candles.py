import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class FundsCandle:
    t: datetime.datetime
    o: float
    h: float
    l: float
    c: float

    def __post_init__(self):
        self.t = format_timestamp(self.t)

    def __repr__(self) -> str:
        result = f"Funds Candle:\n"
        result += f"Time: {self.t}\n"
        result += f"Open: {self.o}\n"
        result += f"High: {self.h}\n"
        result += f"Low: {self.l}\n"
        result += f"Close: {self.c}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class FundsCandlesHumanReadable:
    Date: datetime.datetime
    Open: float
    High: float
    Low: float
    Close: float

    def __post_init__(self):
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        result = f"Funds Candle:\n"
        result += f"Date: {self.Date}\n"
        result += f"Open: {self.Open}\n"
        result += f"High: {self.High}\n"
        result += f"Low: {self.Low}\n"
        result += f"Close: {self.Close}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()
