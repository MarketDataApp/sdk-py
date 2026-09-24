import datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from marketdata.output_types.columns import _column_names
from marketdata.output_types.money import coerce_numbers
from marketdata.utils import format_timestamp


def _join_list(lists: list[list]) -> list:
    return [item for sublist in lists for item in sublist]


@dataclass
class OptionsQuotes:
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
        """List the keys of this model's columns in an API answer."""
        return list(_column_names(OptionsQuotes).values())

    @staticmethod
    def join_dicts(dicts: list[dict], keys: list[str] | None = None) -> dict:
        """Concatenate the symbols' answers column by column.

        ``keys`` are the columns to merge, in their order: ``quotes()`` passes
        the ones it checked every answer for (``utils.json_answer_columns``),
        so the check and the merge cannot disagree. Without them, the columns
        are the model's that the first answer carries. Every answer must carry
        every column: a missing one raises ``KeyError`` instead of shifting the
        rows of the symbols after it. The status flag keeps its place when the
        first answer has one, and is added as ``"ok"`` after the columns when
        it has none, which is the case under ``columns=``.
        """
        if keys is None:
            keys = [key for key in OptionsQuotes.answer_keys() if key in dicts[0]]
        data = {key: _join_list([answer[key] for answer in dicts]) for key in keys}
        if "s" in dicts[0]:
            return {"s": dicts[0]["s"], **data}
        return {**data, "s": "ok"}


@dataclass
class OptionsQuotesHumanReadable:
    api_model: ClassVar[type] = OptionsQuotes

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
        """List the keys of this model's columns in an API answer."""
        return list(_column_names(OptionsQuotesHumanReadable).values())

    @staticmethod
    def join_dicts(dicts: list[dict], keys: list[str] | None = None) -> dict:
        """Concatenate the symbols' answers column by column.

        Args:
            dicts: The answers, in symbol order.
            keys: The columns to merge, in their order. Defaults to the
                model's columns the first answer carries.

        Returns:
            One answer keyed by the API's column names. A human-readable
            answer carries no status flag.

        Raises:
            KeyError: If an answer lacks one of ``keys``.
        """
        if keys is None:
            keys = [
                key
                for key in OptionsQuotesHumanReadable.answer_keys()
                if key in dicts[0]
            ]
        return {key: _join_list([answer[key] for answer in dicts]) for key in keys}
