import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class OptionsChain:
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
        self.updated = [format_timestamp(updated) for updated in self.updated]
        self.expiration = [
            format_timestamp(expiration) for expiration in self.expiration
        ]
        self.firstTraded = [
            format_timestamp(firstTraded) for firstTraded in self.firstTraded
        ]

    def __repr__(self) -> str:
        result = f"Options Chain:\n"
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
        result = f"Options Chain:\n"
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
