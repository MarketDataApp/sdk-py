from abc import ABC, abstractmethod
from dataclasses import is_dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Iterable, Union, get_args, get_origin

if TYPE_CHECKING:
    from marketdata.input_types.base import UserUniversalAPIParams


class BaseOutputHandler(ABC):
    def __init__(
        self,
        data: list[dict] | dict,
        output_schema: type[Any],
        user_universal_params: "UserUniversalAPIParams",
    ):
        self.data = data
        self.output_schema = output_schema
        self.user_universal_params = user_universal_params

    def _type_includes(self, field_type: Any, target: type) -> bool:
        if field_type is target:
            return True

        origin = get_origin(field_type)
        if origin is None:
            return False

        args = get_args(field_type)
        if origin in (list, list, Iterable):
            return any(self._type_includes(arg, target) for arg in args)
        if origin is Union:
            return any(
                self._type_includes(arg, target)
                for arg in args
                if arg is not type(None)
            )
        return False

    def _get_date_columns(self) -> list[str]:
        if not is_dataclass(self.output_schema):
            return []
        fields = self.output_schema.__dataclass_fields__.values()
        return [field.name for field in fields if self._type_includes(field.type, date)]

    def _get_datetime_columns(self) -> list[str]:
        if not is_dataclass(self.output_schema):
            return []
        fields = self.output_schema.__dataclass_fields__.values()
        return [
            field.name for field in fields if self._type_includes(field.type, datetime)
        ]

    def _validate_result(self, result, **kwargs) -> Any:
        return result

    @abstractmethod
    def _get_result(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement this method")

    def get_result(self, *args, **kwargs):
        result = self._get_result(*args, **kwargs)
        return self._validate_result(result, **kwargs)
