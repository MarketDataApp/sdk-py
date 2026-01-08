import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp, resume_long_text


@dataclass
class StockNews:
    symbol: str
    headline: str
    content: str
    source: str
    publicationDate: datetime.datetime
    updated: datetime.datetime

    def __post_init__(self):
        self.publicationDate = format_timestamp(self.publicationDate)
        self.updated = format_timestamp(self.updated)

    def __repr__(self) -> str:
        result = f"Stock News:\n"
        result += f"Symbol: {self.symbol}\n"
        result += f"Headline: {self.headline}\n"
        result += f"Content: {resume_long_text(self.content)}\n"
        result += f"Source: {self.source}\n"
        result += f"Publication Date: {self.publicationDate}\n"
        result += f"Updated: {self.updated}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class StockNewsHumanReadable:
    Symbol: str
    headline: str
    content: str
    source: str
    publicationDate: datetime.datetime
    Date: datetime.datetime

    def __post_init__(self):
        self.publicationDate = format_timestamp(self.publicationDate)
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        result = f"Stock News:\n"
        result += f"Symbol: {self.Symbol}\n"
        result += f"Headline: {self.headline}\n"
        result += f"Content: {resume_long_text(self.content)}\n"
        result += f"Source: {self.source}\n"
        result += f"Publication Date: {self.publicationDate}\n"
        result += f"Date: {self.Date}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()
