import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class FundsCandle:
    t: datetime.datetime
    o: float
    h: float
    # `l` (low) is the API's own field name, and the dataclass fields are the
    # public shape of `OutputFormat.INTERNAL` and of the DataFrame columns, so
    # renaming it to satisfy E741 would be a breaking change.
    l: float  # noqa: E741
    c: float

    def __post_init__(self):
        self.t = format_timestamp(self.t)

    def __repr__(self) -> str:
        result = "Funds Candle:\n"
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
        result = "Funds Candle:\n"
        result += f"Date: {self.Date}\n"
        result += f"Open: {self.Open}\n"
        result += f"High: {self.High}\n"
        result += f"Low: {self.Low}\n"
        result += f"Close: {self.Close}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()


# The API-named twin of the human-readable model, same fields in the same
# order: a `columns=` filter written in API names is translated to the
# human-readable columns by position (#87). Set outside the class so it is
# not a dataclass field.
FundsCandlesHumanReadable.api_model = FundsCandle
