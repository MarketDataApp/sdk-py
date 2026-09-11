import datetime
from dataclasses import dataclass
from decimal import Decimal

from marketdata.output_types.money import coerce_numbers
from marketdata.utils import format_timestamp


@dataclass
class StockCandle:
    t: datetime.datetime
    o: Decimal
    h: Decimal
    # `l` (low) is the API's own field name, and the dataclass fields are the
    # public shape of `OutputFormat.INTERNAL` and of the DataFrame columns, so
    # renaming it to satisfy E741 would be a breaking change.
    l: Decimal  # noqa: E741
    c: Decimal
    v: int

    def __post_init__(self):
        coerce_numbers(self)
        self.t = format_timestamp(self.t)

    def __repr__(self) -> str:
        result = "Stock Candles:\n"
        result += f"Time: {self.t}\n"
        result += f"Open: {self.o}\n"
        result += f"High: {self.h}\n"
        result += f"Low: {self.l}\n"
        result += f"Close: {self.c}\n"
        result += f"Volume: {self.v}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class StockCandlesHumanReadable:
    Date: datetime.datetime
    Open: Decimal
    High: Decimal
    Low: Decimal
    Close: Decimal
    Volume: int

    def __post_init__(self):
        coerce_numbers(self)
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        result = "Stock Candle:\n"
        result += f"Date: {self.Date}\n"
        result += f"Open: {self.Open}\n"
        result += f"High: {self.High}\n"
        result += f"Low: {self.Low}\n"
        result += f"Close: {self.Close}\n"
        result += f"Volume: {self.Volume}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()
