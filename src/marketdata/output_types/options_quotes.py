import datetime
from dataclasses import dataclass

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
    def join_dicts(dicts: list[dict]) -> dict:
        data = {
            field: _join_list([dict.get(field, []) for dict in dicts])
            for field in OptionsQuotes.__dataclass_fields__
            if field in dicts[0].keys()
        }
        data["s"] = dicts[0].get("s", "ok")
        return data

    @staticmethod
    def get_null_dict() -> dict:
        data = {field: [] for field in OptionsQuotes.__dataclass_fields__}
        data.pop("s")
        return data

    @staticmethod
    def get_null_csv_string(add_headers: bool = False) -> str:
        text = ",".join([""] * len(OptionsQuotes.__dataclass_fields__))
        if add_headers:
            text = ",".join(OptionsQuotes.__dataclass_fields__) + "\n" + text
        return text


@dataclass
class OptionsQuotesHumanReadable:
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
    def join_dicts(dicts: list[dict]) -> dict:
        data = {
            _to_internal_field(field): _join_list(
                [dict[_to_human_readable_field(field)] for dict in dicts]
            )
            for field in OptionsQuotesHumanReadable.__dataclass_fields__
            if _to_human_readable_field(field) in dicts[0].keys()
        }
        return data

    @staticmethod
    def get_null_dict() -> dict:
        data = {
            field.replace("_", " "): []
            for field in OptionsQuotesHumanReadable.__dataclass_fields__
        }
        return data

    @staticmethod
    def get_null_csv_string(add_headers: bool = False) -> str:
        text = ",".join([""] * len(OptionsQuotesHumanReadable.__dataclass_fields__))
        if add_headers:
            text = (
                ",".join(
                    [
                        field.replace("_", " ")
                        for field in OptionsQuotesHumanReadable.__dataclass_fields__
                    ]
                )
                + "\n"
                + text
            )
        return text
