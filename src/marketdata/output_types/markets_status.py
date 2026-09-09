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


# The API-named twin of the human-readable model: a `columns=` filter written
# in API names is translated to the human-readable columns by position (#87).
# Set outside the class so it is not a dataclass field.
#
# This is the one pair whose fields are NOT in the same order (`date, status`
# against `Status, Date`). It stays correct because both API names already
# match a human-readable column through `column_key`, so `model_columns` never
# falls back to the positional map here; renaming either column so that it no
# longer matches would silently select the wrong one.
# `test_output_types.py::test_every_api_model_twin_lines_up_with_its_model`
# pins what the translation actually relies on.
MarketStatusHumanReadable.api_model = MarketStatus
