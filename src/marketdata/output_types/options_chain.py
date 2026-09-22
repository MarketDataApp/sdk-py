import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from marketdata.output_types.money import coerce_numbers
from marketdata.utils import format_timestamp


@dataclass
class OptionsChain:
    s: str
    optionSymbol: list[str]
    underlying: list[str]
    expiration: list[datetime.datetime | None]
    side: list[str]
    strike: list[Decimal]
    firstTraded: list[datetime.datetime | None]
    dte: list[int]
    updated: list[datetime.datetime | None]
    bid: list[Decimal]
    bidSize: list[int]
    mid: list[Decimal]
    ask: list[Decimal]
    askSize: list[int]
    last: list[Decimal]
    openInterest: list[int]
    volume: list[int]
    inTheMoney: list[bool]
    intrinsicValue: list[Decimal]
    extrinsicValue: list[Decimal]
    underlyingPrice: list[Decimal]
    iv: list[float]
    delta: list[float]
    gamma: list[float]
    theta: list[float]
    vega: list[float]

    def __post_init__(self):
        """Give the numbers their annotated types and read the dates; a null date stays ``None``."""
        coerce_numbers(self)
        self.updated = [
            None if updated is None else format_timestamp(updated)
            for updated in self.updated
        ]
        self.expiration = [
            None if expiration is None else format_timestamp(expiration)
            for expiration in self.expiration
        ]
        self.firstTraded = [
            None if firstTraded is None else format_timestamp(firstTraded)
            for firstTraded in self.firstTraded
        ]

    def __repr__(self) -> str:
        result = "Options Chain:\n"
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


@dataclass
class OptionsChainHumanReadable:
    api_model: ClassVar[type] = OptionsChain

    Symbol: list[str]
    Underlying: list[str]
    Expiration_Date: list[datetime.datetime | None]
    Option_Side: list[str]
    Strike: list[Decimal]
    First_Traded: list[datetime.datetime | None]
    Days_To_Expiration: list[int]
    Date: list[datetime.datetime | None]
    Bid: list[Decimal]
    Bid_Size: list[int]
    Mid: list[Decimal]
    Ask: list[Decimal]
    Ask_Size: list[int]
    Last: list[Decimal]
    Open_Interest: list[int]
    Volume: list[int]
    In_The_Money: list[bool]
    Intrinsic_Value: list[Decimal]
    Extrinsic_Value: list[Decimal]
    Underlying_Price: list[Decimal]
    IV: list[float]
    Delta: list[float]
    Gamma: list[float]
    Theta: list[float]
    Vega: list[float]

    def __post_init__(self):
        """Give the numbers their annotated types and read the dates; a null date stays ``None``."""
        coerce_numbers(self)
        self.Expiration_Date = [
            None if expiration is None else format_timestamp(expiration)
            for expiration in self.Expiration_Date
        ]
        self.First_Traded = [
            None if firstTraded is None else format_timestamp(firstTraded)
            for firstTraded in self.First_Traded
        ]
        self.Date = [
            None if date is None else format_timestamp(date) for date in self.Date
        ]

    def __repr__(self) -> str:
        result = "Options Chain:\n"
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
