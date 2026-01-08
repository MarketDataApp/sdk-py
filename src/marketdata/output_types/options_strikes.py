import datetime
from dataclasses import dataclass, fields
from typing import Any

from marketdata.utils import format_timestamp


@dataclass
class OptionsStrikes:
    s: str
    updated: datetime.datetime

    def __post_init__(self):
        self.updated = format_timestamp(self.updated)

    def __init__(self, **kwargs: Any):
        fixed = {f.name for f in fields(self)}

        for k, v in kwargs.items():
            if k not in fixed:
                v = self._to_float_list(k, v)
            setattr(self, k, v)

        setattr(self, "updated", format_timestamp(kwargs["updated"]))

    @staticmethod
    def _to_float_list(name: str, v: Any):
        if not isinstance(v, (list, tuple)):
            raise TypeError(f"extra field '{name}' must be a list of floats")
        return v

    def __repr__(self) -> str:
        extra_kwargs = {
            k: v for k, v in self.__dict__.items() if k not in ["s", "updated"]
        }
        message = "Strikes:\n"
        for k, v in extra_kwargs.items():
            message += f"{k}: {len(v)}\n"
        return message

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class OptionsStrikesHumanReadable:
    Date: datetime.datetime

    def __post_init__(self):
        self.Date = format_timestamp(self.Date)

    def __init__(self, **kwargs: Any) -> None:
        fixed = {f.name for f in fields(self)}

        for k, v in kwargs.items():
            if k not in fixed:
                v = self._to_float_list(k, v)
            setattr(self, k, v)

        setattr(self, "Date", format_timestamp(kwargs["Date"]))

    @staticmethod
    def _to_float_list(name: str, v: Any):
        if not isinstance(v, (list, tuple)):
            raise TypeError(f"extra field '{name}' must be a list of floats")
        return v

    def __repr__(self) -> str:
        _list_to_string = lambda lst: "\n".join([str(item) for item in lst])
        extra_kwargs = {k: v for k, v in self.__dict__.items() if k not in ["Date"]}
        result = f"Options Strikes:\n"
        result += f"Dates:\n"
        for k, v in extra_kwargs.items():
            result += f"{k}: {len(v)}\n"
        return result

    def __str__(self) -> str:
        return self.__repr__()
