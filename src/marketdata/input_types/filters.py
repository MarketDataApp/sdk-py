"""The numeric filters of ``options.chain``: ``strike`` and ``delta`` (#101).

The API reads both as a small expression language rather than as one number
(``common/util/input_validation_helper.py``, ``parse_numeric_query`` and
``parse_input_expression``): ``250`` is one value, ``250,255`` a set,
``250-260`` an inclusive range, and ``>=250`` a one-sided bound. Written as a
string that grammar is easy to get wrong and invisible to a type checker, so
each shape has a constructor, the way sdk-go gives them. sdk-csharp names
three of these shapes and has no filter for ``delta`` at all.

Three of its rules are sharp edges, measured against production on
2026-09-15 and 2026-09-17:

- ``parse_input`` is ``abs(float(value))``, so a minus sign is dropped without
  a word. ``strike=-250`` answers with the strikes at ``250``.
- ``parse_input_expression`` skips the range branch when the text opens with a
  minus, so ``-0.5-0.5`` reaches ``float()`` whole and the call fails with a
  ``400``.
- Otherwise, text with no comma and no comparison is split at a minus as a
  range, even at a minus inside a number: ``delta=5e-05`` is split into
  ``5e`` and ``05`` and fails with a ``400``, while ``delta=0.00005`` is
  read. After a comparison, and in a list of several values, each number is
  read whole.

So a number is sent as plain digits, and one a float cannot hold is refused,
since ``float()`` would read it as an infinity or as zero. Where a negative
changes what the caller asked for, it is refused here with a message rather
than sent. ``delta`` is the exception the API documents: it
filters on the absolute value and answers both sides, so ``0.5`` and ``-0.5``
return the same rows, verified, and both are accepted for a single value.
"""

from __future__ import annotations

import math
import numbers
import sys
from decimal import Decimal
from typing import TypeVar

__all__ = ["DeltaFilter", "StrikeFilter"]

# What a constructor returns: the class it was called on, so a type checker
# sees a `StrikeFilter` or a `DeltaFilter` rather than the private base.
_Filter = TypeVar("_Filter", bound="_NumericFilter")

# The last decimal place a float can hold: that of its smallest step above
# zero. `from_float` is the conversion a `FloatOperation` trap allows, so
# importing this module neither trips nor flags a caller who sets one.
_LAST_PLACE = Decimal.from_float(math.ulp(0.0)).adjusted()


def _too_far(argument: str, shown: str) -> str:
    return (
        f"{argument} is too far from zero for a float ({shown}): the API would "
        "read it as an infinity"
    )


def _too_close(argument: str, shown: str) -> str:
    return (
        f"{argument} is too close to zero for a float ({shown}): the API would "
        "read it as 0"
    )


def _render(
    value: object, argument: str, *, negative_ok: bool, in_a_range: bool = False
) -> str:
    """One number as the digits the API should read.

    The digits are the ones the caller named, written out in full: a
    ``Decimal`` keeps its trailing zeros, a float is written from its shortest
    form, so ``65.1`` is sent as ``65.1``, and no number travels in exponent
    form. Any other real number is turned into a float first, so a numpy
    ``float32`` travels with the digits of that float.
    ``Decimal("250.00").normalize()`` is ``Decimal("2.5E+2")`` and is sent as
    ``250``. ``1e-05`` is sent as ``0.00001``, which the API reads in every
    shape, while the exponent form is split at its minus when it stands alone
    or sits in a range.

    The API reads each number with ``float()``, so a number a float cannot
    hold is refused: too far from zero, it would be read as an infinity, and
    too close to zero, as 0. Both are checked before the digits are written,
    since an exponent can ask for more of them than there is memory for. A
    zero cannot be too close, so one written past a float's last decimal
    place is sent as ``0``.
    """
    if isinstance(value, bool):
        raise ValueError(f"{argument} cannot be a bool: {value!r}")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{argument} must be a finite number, not {value!r}")
        number, as_float = value, float(value)
        shown = f"{number:.3e}"
    elif isinstance(value, numbers.Integral):
        whole = int(value)
        shown = f"an integer of {whole.bit_length()} bits"
        if whole.bit_length() > sys.float_info.max_exp:
            # Before `Decimal(whole)`, which takes quadratic time on the digits.
            raise ValueError(_too_far(argument, shown))
        number = Decimal(whole)
        as_float = float(number)
    elif isinstance(value, numbers.Real):
        shown = f"a {type(value).__name__}"
        try:
            as_float = float(value)
        except OverflowError:
            raise ValueError(_too_far(argument, shown)) from None
        if math.isnan(as_float) or (math.isinf(as_float) and as_float == value):
            raise ValueError(f"{argument} must be a finite number, not {value!r}")
        number = Decimal(str(as_float))
    else:
        raise ValueError(f"{argument} must be a number, not {type(value).__name__}")

    if math.isinf(as_float):
        raise ValueError(_too_far(argument, shown))
    if as_float == 0 and value != 0:
        raise ValueError(_too_close(argument, shown))

    if number == 0:
        # `-0.0` is zero and the API answers `0` for it, so the sign goes
        # rather than the value being refused for a minus nobody wrote.
        if number.adjusted() < _LAST_PLACE:
            return "0"
        return f"{number:f}".lstrip("-")
    rendered = f"{number:f}"
    if not negative_ok and rendered.startswith("-"):
        if in_a_range:
            raise ValueError(
                f"{argument} cannot be negative ({rendered}): a range with a "
                "minus in it is not read as a range at all, so the call fails "
                "with a 400"
            )
        raise ValueError(
            f"{argument} cannot be negative ({rendered}): the API reads a "
            "number by its absolute value, so it would answer for "
            f"{rendered[1:]} instead of failing"
        )
    return rendered


class _NumericFilter(str):
    """A filter rendered as the expression the API reads.

    A ``str``, so it reaches the query string with no handling of its own and
    a caller can print or compare it like any other string. Being a ``str``
    also means the class is open: ``StrikeFilter("ATM")`` builds an instance
    without passing through any constructor here, and the API answers that one
    with a ``400``. The constructors are the checked way in, not a wall;
    sdk-csharp, whose union is sealed, can close what Python cannot.
    """

    __slots__ = ()

    _WHAT = "value"
    _SINGLE_NEGATIVE_OK = False

    @classmethod
    def _single(cls: type[_Filter], value: object) -> _Filter:
        """One value. Each filter names this for what the API does with it."""
        return cls(_render(value, cls._WHAT, negative_ok=cls._SINGLE_NEGATIVE_OK))

    @classmethod
    def any_of(cls: type[_Filter], *values: object) -> _Filter:
        """A set of values, sent as a comma list.

        Both sides come back at each one unless ``side`` narrows it, which is
        how a spread is priced in one request instead of one call per leg.
        """
        if not values:
            raise ValueError(f"any_of needs at least one {cls._WHAT}")
        return cls(
            ",".join(
                _render(value, cls._WHAT, negative_ok=cls._SINGLE_NEGATIVE_OK)
                for value in values
            )
        )

    @classmethod
    def between(cls: type[_Filter], low: object, high: object) -> _Filter:
        """An inclusive range, sent as ``low-high``."""
        rendered_low = _render(low, "low", negative_ok=False, in_a_range=True)
        rendered_high = _render(high, "high", negative_ok=False, in_a_range=True)
        if Decimal(rendered_low) > Decimal(rendered_high):
            raise ValueError(
                f"low must not be above high: {rendered_low}-{rendered_high}"
            )
        return cls(f"{rendered_low}-{rendered_high}")

    @classmethod
    def at_least(cls: type[_Filter], value: object) -> _Filter:
        """At or above a value, sent as ``>=value``."""
        return cls(f">={_render(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def at_most(cls: type[_Filter], value: object) -> _Filter:
        """At or below a value, sent as ``<=value``."""
        return cls(f"<={_render(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def above(cls: type[_Filter], value: object) -> _Filter:
        """Strictly above a value, sent as ``>value``."""
        return cls(f">{_render(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def below(cls: type[_Filter], value: object) -> _Filter:
        """Strictly below a value, sent as ``<value``."""
        return cls(f"<{_render(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def expression(cls: type[_Filter], text: str) -> _Filter:
        """An expression written by hand, passed through as it is.

        The escape hatch for a shape the constructors above do not name, the
        way ``StrikeExpr`` is in sdk-go. Nothing is checked beyond it being a
        non-empty string: the API decides.
        """
        if not isinstance(text, str):
            raise ValueError(f"an expression must be a str, not {type(text).__name__}")
        if not text.strip():
            raise ValueError("an expression cannot be empty")
        return cls(text)


class StrikeFilter(_NumericFilter):
    """The ``strike`` filter of ``options.chain``.

    ``StrikeFilter.between(250, 260)`` renders ``250-260``. A negative is
    refused everywhere: there is no negative strike, and the API would answer
    for its absolute value without saying so.
    """

    __slots__ = ()

    _WHAT = "strike"
    _SINGLE_NEGATIVE_OK = False

    @classmethod
    def exact(cls: type[_Filter], value: object) -> _Filter:
        """One strike, which the API matches exactly."""
        return cls._single(value)


class DeltaFilter(_NumericFilter):
    """The ``delta`` filter of ``options.chain``.

    Three things the API does with this parameter are worth knowing before
    the constructors make sense.

    It matches the **nearest** delta rather than the one asked for: per
    expiration and side it sorts by distance and takes the closest, so
    ``nearest(0.5)`` answered ``[0.5266, -0.4729]`` when it was measured, and
    it never answers with nothing. That is why its single-value constructor
    is ``nearest``, where ``StrikeFilter`` has ``exact``.

    It filters on the **absolute value** and answers both sides, so ``0.5``
    and ``-0.5`` return the same rows, measured. Both are accepted for a
    single value and for a set.

    A value above 1 is read as a percentage: ``nearest(30)`` means ``0.30``.

    A negative is still refused in a range or a bound, where the absolute
    value changes the question rather than restating it: ``>=-0.5`` would ask
    the API for ``>=0.5``, and ``-0.5-0.5`` is not read as a range at all and
    fails with a ``400``.

    The filter can also do nothing at all: if any contract in the chain the
    API fetched carries a null delta, the whole filter is skipped and the full
    chain comes back with a ``200`` (MarketData-App/api#352). Together with a
    historical ``date`` it is refused with a ``400``.
    """

    __slots__ = ()

    _WHAT = "delta"
    _SINGLE_NEGATIVE_OK = True

    @classmethod
    def nearest(cls: type[_Filter], value: object) -> _Filter:
        """One delta. The API answers with the contract whose delta is nearest to
        it, per expiration and side."""
        return cls._single(value)


def _render_number(value: object, argument: str) -> str:
    """A bare number for one of these parameters, as its digits.

    The field validators use it so a caller who passes a plain number gets the
    same reading, and the same refusals, as one who builds a filter.
    """
    return _render(value, argument, negative_ok=argument == "delta")
