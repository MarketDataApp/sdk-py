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
    have, and NaN, which is how pandas writes that same missing value, becomes
    ``None`` too. An infinity is not an amount. An integer is exact as it is.
    Any other number goes through its shortest repr in its own precision, so
    ``65.1`` becomes ``Decimal("65.1")`` whether it is a float, a numpy
    float64 or a float32, rather than the binary expansion ``Decimal(65.1)``
    would give. The API path never hands this a float, since it parses
    amounts as Decimals in the first place, so that rule is for a model built
    by hand. A ``str`` must be a decimal number.

    Raises ``TypeError`` for a value that is not a number and ``ValueError``
    for one that is not a finite amount.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"an amount cannot be a bool: {value!r}")
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, numbers.Integral):
        return Decimal(int(value))
    elif isinstance(value, (str, numbers.Real)):
        amount = _parse_decimal(value)
    else:
        raise TypeError(f"an amount must be a number, not {type(value).__name__}")
    if amount.is_finite():
        return amount
    if amount.is_nan():
        return None
    raise ValueError(f"an amount must be finite, not {value!r}")


def _parse_decimal(value: str | numbers.Real) -> Decimal:
    # str() is the shortest repr in the value's own precision: "65.1" for a
    # float, for a numpy float64 (whose repr is "np.float64(65.1)") and for a
    # float32, which is not a float at all.
    try:
        return Decimal(str(value))
    except InvalidOperation:
        if isinstance(value, str):
            raise ValueError(f"not a decimal number: {value!r}") from None
    try:
        # A Real whose str is not a decimal, such as a Fraction.
        return Decimal(repr(float(value)))
    except (ArithmeticError, ValueError):
        raise ValueError(f"not a decimal number: {value!r}") from None


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


def _is_amount(value: Any) -> bool:
    """Already what a money field holds: ``None`` or a finite ``Decimal``,
    which is every amount the exact parse produces."""
    return value is None or (isinstance(value, Decimal) and value.is_finite())


def _as_money(value: Any) -> Any:
    if isinstance(value, list):
        return [item if _is_amount(item) else to_decimal(item) for item in value]
    if isinstance(value, tuple):
        return tuple(item if _is_amount(item) else to_decimal(item) for item in value)
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
    would. The conversion applies to each amount: the shape of a field (a
    scalar or a list) is not checked, as it never was. A scalar that already
    holds the right type, and a list with no ``Decimal`` in a field that is
    not money, are left alone, which is every field of a record row."""
    for name, money in _number_fields(type(instance)):
        value = getattr(instance, name)
        if money:
            if _is_amount(value):
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
        except (TypeError, ValueError) as exc:
            raise type(exc)(f"{type(instance).__name__}.{name}: {exc}") from exc
        setattr(instance, name, converted)
