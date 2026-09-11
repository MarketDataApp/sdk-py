import datetime
from dataclasses import dataclass, fields
from typing import ClassVar

from marketdata.utils import format_timestamp


def _join_list(lists: list[list]) -> list:
    return [item for sublist in lists for item in sublist]


def _to_internal_field(field: str) -> str:
    """`Expiration Date` as the API sends it, `Expiration_Date` as the model
    names it."""
    return field.replace(" ", "_")


def _to_human_readable_field(field: str) -> str:
    return field.replace("_", " ")


@dataclass
class OptionsQuotes:
    s: str
    optionSymbol: list[str]
    underlying: list[str]
    expiration: list[datetime.datetime]
    side: list[str]
    strike: list[float]
    firstTraded: list[datetime.datetime]
    dte: list[int]
    updated: list[datetime.datetime]
    bid: list[float]
    bidSize: list[int]
    mid: list[float]
    ask: list[float]
    askSize: list[int]
    last: list[float]
    openInterest: list[int]
    volume: list[int]
    inTheMoney: list[bool]
    intrinsicValue: list[float]
    extrinsicValue: list[float]
    underlyingPrice: list[float]
    iv: list[float]
    delta: list[float]
    gamma: list[float]
    theta: list[float]
    vega: list[float]

    def __post_init__(self):
        self.updated = [
            format_timestamp(updated) for updated in self.updated if updated
        ]
        self.expiration = [
            format_timestamp(expiration) for expiration in self.expiration if expiration
        ]
        self.firstTraded = [
            format_timestamp(firstTraded)
            for firstTraded in self.firstTraded
            if firstTraded
        ]

    def __repr__(self) -> str:
        result = "Options Quotes:\n"
        result += f"Symbol: {len(self.optionSymbol)} options\n"
        result += f"Underlying: {len(self.underlying)} underlying\n"
        result += f"Expiration: {len(self.expiration)} expirations\n"
        result += f"Side: {len(self.side)} sides\n"
        result += f"Strike: {len(self.strike)} strikes\n"
        result += f"First Traded: {len(self.firstTraded)} first traded\n"
        result += f"DTE: {len(self.dte)} DTE\n"
        result += f"Updated: {len(self.updated)} updated\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()

    @staticmethod
    def answer_keys() -> list[str]:
        """The keys of this model's columns in an API answer. The status flag
        ``s`` is not a column."""
        return [field.name for field in fields(OptionsQuotes) if field.name != "s"]

    @staticmethod
    def join_dicts(dicts: list[dict]) -> dict:
        """Concatenate the symbols' answers column by column, keeping the
        columns the first answer carries. Every answer must carry them: a
        missing one raises ``KeyError`` instead of shifting the rows of the
        symbols after it. ``quotes()`` checks the answers first, so there it
        is a ``ParseError`` naming the symbol."""
        data = {
            key: _join_list([answer[key] for answer in dicts])
            for key in OptionsQuotes.answer_keys()
            if key in dicts[0]
        }
        return {"s": dicts[0].get("s", "ok"), **data}


@dataclass
class OptionsQuotesHumanReadable:
    api_model: ClassVar[type] = OptionsQuotes

    Symbol: list[str]
    Underlying: list[str]
    Expiration_Date: list[datetime.datetime]
    Option_Side: list[str]
    Strike: list[float | int]
    First_Traded: list[datetime.datetime]
    Days_To_Expiration: list[int]
    Date: list[datetime.datetime]
    Bid: list[float]
    Bid_Size: list[int]
    Mid: list[float]
    Ask: list[float]
    Ask_Size: list[int]
    Last: list[float]
    Open_Interest: list[int]
    Volume: list[int]
    In_The_Money: list[bool]
    Intrinsic_Value: list[float]
    Extrinsic_Value: list[float]
    Underlying_Price: list[float]
    IV: list[float]
    Delta: list[float]
    Gamma: list[float]
    Theta: list[float]
    Vega: list[float]

    def __post_init__(self):
        self.Expiration_Date = [
            format_timestamp(expiration) for expiration in self.Expiration_Date
        ]
        self.First_Traded = [
            format_timestamp(firstTraded) for firstTraded in self.First_Traded
        ]
        self.Date = [format_timestamp(date) for date in self.Date]

    def __repr__(self) -> str:
        result = "Options Quotes:\n"
        result += f"Underlying: {len(self.Underlying)} underlying\n"
        result += f"Expiration Date: {len(self.Expiration_Date)} expiration dates\n"
        result += f"Option Side: {len(self.Option_Side)} sides\n"
        result += f"Strike: {len(self.Strike)} strikes\n"
        result += f"First Traded: {len(self.First_Traded)} first traded\n"
        result += f"Days To Expiration: {len(self.Days_To_Expiration)} DTE\n"
        result += f"Last: {len(self.Last)} last\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()

    @staticmethod
    def answer_keys() -> list[str]:
        """The keys of this model's columns in an API answer: the field names
        spelled with the API's spaces (``Expiration Date``)."""
        return [
            _to_human_readable_field(field.name)
            for field in fields(OptionsQuotesHumanReadable)
        ]

    @staticmethod
    def join_dicts(dicts: list[dict]) -> dict:
        """Concatenate the symbols' answers column by column, as
        :meth:`OptionsQuotes.join_dicts` does, under the model's field
        names."""
        return {
            _to_internal_field(key): _join_list([answer[key] for answer in dicts])
            for key in OptionsQuotesHumanReadable.answer_keys()
            if key in dicts[0]
        }
