import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class OptionsExpirations:
    s: str
    expirations: list[datetime.datetime]
    updated: datetime.datetime | None = None

    def __post_init__(self):
        if self.updated is not None:
            self.updated = format_timestamp(self.updated)
        self.expirations = [
            format_timestamp(expiration) for expiration in self.expirations
        ]

    def __repr__(self) -> str:
        expirations = [
            expiration.strftime("%Y-%m-%d") for expiration in self.expirations
        ]
        expirations_string = "\n".join(expirations)
        return f"Expirations:\n{expirations_string}\n"

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class OptionsExpirationsHumanReadable:
    Expirations: list[datetime.datetime]
    Date: datetime.datetime

    def __post_init__(self):
        self.Expirations = [
            format_timestamp(expiration) for expiration in self.Expirations
        ]
        self.Date = format_timestamp(self.Date)

    def __repr__(self) -> str:
        expirations = [
            expiration.strftime("%Y-%m-%d") for expiration in self.Expirations
        ]
        expirations_string = "\n".join(expirations)
        return f"Expirations:\n{expirations_string}\n"

    def __str__(self) -> str:
        return self.__repr__()


# The API-named twin of the human-readable model, same fields in the same
# order: a `columns=` filter written in API names is translated to the
# human-readable columns by position (#87). Set outside the class so it is
# not a dataclass field.
OptionsExpirationsHumanReadable.api_model = OptionsExpirations
