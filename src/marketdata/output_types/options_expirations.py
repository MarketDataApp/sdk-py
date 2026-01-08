import datetime
from dataclasses import dataclass

from marketdata.utils import format_timestamp


@dataclass
class OptionsExpirations:
    s: str
    expirations: list[datetime.datetime]
    updated: datetime.datetime

    def __post_init__(self):
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
