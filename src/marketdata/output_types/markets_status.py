import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class MarketStatus:
    date: datetime.date
    status: str

    def __post_init__(self):
        self.date = format_timestamp(self.date)

    def __repr__(self) -> str:
        return f"Market Status: {self.status}, Date: {self.date}"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class MarketStatusHumanReadable:
    Status: str
    Date: datetime.datetime

    def __post_init__(self):
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        return f"Market Status: {self.Status}, Date: {self.Date}"

    def __str__(self) -> str:
        return self.__repr__()
