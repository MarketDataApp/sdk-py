import types
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Iterable, Union, get_args, get_origin

from marketdata.input_types.base import DateFormat
from marketdata.output_types.columns import column_types, model_columns

if TYPE_CHECKING:
    from marketdata.input_types.base import UserUniversalAPIParams


def _scalar_type(annotation: Any) -> Any:
    """Unwrap ``list[X]`` and ``X | None`` down to ``X``.

    Args:
        annotation: A field annotation of an output model.

    Returns:
        The scalar type, or ``None`` for a union of several types.
    """
    origin = get_origin(annotation)
    if origin in (list, Iterable):
        return _scalar_type(get_args(annotation)[0])
    if origin is Union or origin is types.UnionType:
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        return _scalar_type(args[0]) if len(args) == 1 else None
    return annotation


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
        # Handle both typing.Union[X, None] and the PEP 604 `X | None` form,
        # whose origin is types.UnionType rather than typing.Union.
        if origin is Union or origin is types.UnionType:
            return any(
                self._type_includes(arg, target)
                for arg in args
                if arg is not type(None)
            )
        return False

    def _columns_of_type(self, target: type) -> list[str]:
        """List the columns whose field annotation includes ``target``.

        Args:
            target: The type to look for.

        Returns:
            The column names, as the API spells them.
        """
        return [
            column
            for column, annotation in column_types(self.output_schema).items()
            if self._type_includes(annotation, target)
        ]

    def _get_date_columns(self) -> list[str]:
        """List the columns annotated as dates."""
        return self._columns_of_type(date)

    def _get_datetime_columns(self) -> list[str]:
        """List the columns annotated as datetimes."""
        return self._columns_of_type(datetime)

    def _column_order(self, present: list[str]) -> list[str]:
        """Order the columns of a result like the model.

        Args:
            present: The columns the result has.

        Returns:
            The present columns in model order or, under a ``columns=`` filter,
            in request order. Columns the model does not name go last.
        """
        known = model_columns(self.output_schema, self.user_universal_params.columns)
        order = [column for column in known if column in present]
        return order + [column for column in present if column not in order]

    def _column_kinds(self) -> dict[str, type]:
        """Map each column to the kind of value its annotation promises.

        Returns:
            ``float`` (money included), ``int``, ``bool`` or ``str`` per
            column. A date column gets the type the API sends it as: ``str``
            under ``DateFormat.TIMESTAMP``, ``float`` under
            ``DateFormat.SPREADSHEET`` and ``int`` otherwise. Columns of any
            other type are left out.
        """
        date_format = self.user_universal_params.date_format
        date_kind = {DateFormat.TIMESTAMP: str, DateFormat.SPREADSHEET: float}.get(
            date_format, int
        )
        kinds = {}
        for column, annotation in column_types(self.output_schema).items():
            scalar = _scalar_type(annotation)
            if scalar in (date, datetime):
                kinds[column] = date_kind
            elif scalar is Decimal:
                kinds[column] = float
            elif scalar in (float, int, bool, str):
                kinds[column] = scalar
        return kinds

    def _validate_result(self, result, **kwargs) -> Any:
        return result

    @abstractmethod
    def _get_result(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement this method")

    def get_result(self, *args, **kwargs):
        result = self._get_result(*args, **kwargs)
        return self._validate_result(result, **kwargs)
