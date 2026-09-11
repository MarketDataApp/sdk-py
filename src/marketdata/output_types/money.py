"""The number types of the output models (#50).

Money is a ``Decimal``: a binary float cannot hold most decimal amounts, so a
price that is compared, rounded or summed as a float drifts (``0.1 + 0.2 !=
0.3``). Every other number keeps the type the plain JSON parse gives it:
``float`` for greeks, implied volatility and percentages, ``int`` for sizes
and counts.

``OutputFormat.INTERNAL`` decodes the body of a resource with money fields
with ``parse_json(response, exact=True)``, so an amount is built from the
digits the API wrote and never passes through a float. That parse turns every
number with a fraction into a ``Decimal``, money or not, so each of those
models calls ``coerce_numbers`` first thing in ``__post_init__``: a field
annotated ``Decimal`` (or ``list[Decimal]``) holds Decimals, and every other
field gets back exactly the float the plain parse would have given it.
"""

import dataclasses
import numbers
import types
from decimal import Decimal, InvalidOperation
from functools import cache
from typing import Any, Union, get_args, get_origin, get_type_hints


def to_decimal(value: Any) -> Decimal | None:
    """An amount as a ``Decimal``.

    ``None`` stays ``None``: the API sends ``null`` for a price it does not
    have. An integer is exact as it is. A float goes through its shortest
    repr, so ``65.1`` becomes ``Decimal("65.1")`` rather than the binary
    expansion ``Decimal(65.1)`` would give. The API path never hands this a
    float, since it parses amounts as Decimals in the first place, so that
    rule is for a model built by hand, numpy scalars included. A ``str`` must
    be a decimal number.
    """
    if value is None or isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError(f"an amount cannot be a bool: {value!r}")
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            raise ValueError(f"not a decimal number: {value!r}") from None
    if isinstance(value, numbers.Integral):
        return Decimal(int(value))
    if isinstance(value, numbers.Real):
        # float() first: numpy's float64 is a float whose repr is
        # "np.float64(65.1)", and a float32 is not a float at all.
        return Decimal(repr(float(value)))
    raise TypeError(f"an amount must be a number, not {type(value).__name__}")


def decimal_to_float(value: Any) -> Any:
    """The float the plain parse gives a number the exact parse made a
    ``Decimal``; any other value is returned as it is.

    ``float(Decimal(text))`` reads the Decimal's own digits, so it is the same
    float ``float(text)`` is: a greek or a spreadsheet date comes out
    bit-identical to what the model held before #50.
    """
    return float(value) if isinstance(value, Decimal) else value


def _holds_decimal(annotation: Any) -> bool:
    if annotation is Decimal:
        return True
    if get_origin(annotation) in (list, tuple, Union, types.UnionType):
        return any(_holds_decimal(arg) for arg in get_args(annotation))
    return False


@cache
def decimal_fields(model: type) -> frozenset[str]:
    """The fields of ``model`` whose annotation says they hold money."""
    hints = get_type_hints(model)
    return frozenset(
        field.name
        for field in dataclasses.fields(model)
        if _holds_decimal(hints[field.name])
    )


@cache
def _number_fields(model: type) -> tuple[tuple[str, bool], ...]:
    """Every field of ``model`` with whether it holds money, worked out once
    per class: a model is built once per row of a response."""
    money = decimal_fields(model)
    return tuple(
        (field.name, field.name in money) for field in dataclasses.fields(model)
    )


def _as_money(value: Any) -> Any:
    if isinstance(value, list):
        return [
            item if isinstance(item, Decimal) else to_decimal(item) for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            item if isinstance(item, Decimal) else to_decimal(item) for item in value
        )
    return to_decimal(value)


def _as_parsed(value: Any) -> Any:
    if isinstance(value, list):
        return [decimal_to_float(item) for item in value]
    if isinstance(value, tuple):
        return tuple(decimal_to_float(item) for item in value)
    return decimal_to_float(value)


def coerce_numbers(instance: Any) -> None:
    """Give every number field of a model instance the type its annotation
    promises: Decimals for the money fields, and for every other field the
    float the plain parse gives in place of any ``Decimal`` the exact parse
    left there. A dataclass does not enforce its annotations, so nothing else
    would. A field that already holds what it should is left alone, which is
    every field of most rows."""
    for name, money in _number_fields(type(instance)):
        value = getattr(instance, name)
        if money:
            if value is None or isinstance(value, Decimal):
                continue
            convert = _as_money
        elif isinstance(value, Decimal) or (
            isinstance(value, (list, tuple))
            and any(isinstance(item, Decimal) for item in value)
        ):
            convert = _as_parsed
        else:
            continue
        try:
            converted = convert(value)
        except (TypeError, ValueError, ArithmeticError) as exc:
            raise type(exc)(f"{type(instance).__name__}.{name}: {exc}") from exc
        setattr(instance, name, converted)
