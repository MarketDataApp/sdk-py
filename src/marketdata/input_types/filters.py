"""The ``strike`` and ``delta`` filters of ``options.chain``.

The API reads both as an expression: ``250`` is one value, ``250,255`` a set,
``250-260`` an inclusive range, and ``>=250`` or ``<250`` a one-sided bound.
``StrikeFilter`` and ``DeltaFilter`` build each shape from numbers.

A number is sent as plain digits, never in exponent form: the API splits a lone
value or a range at any minus, so ``delta=5e-05`` fails with a ``400``. A number
a float cannot hold is refused, since the API would read it as an infinity or
as 0. A negative is refused where the API would answer a different question or
fail: it reads a number by its absolute value, so ``strike=-250`` answers for
``250``, and ``-0.5-0.5`` is not read as a range and fails with a ``400``. A
single ``delta`` or a set of them may be negative, since the API filters delta
on its absolute value and answers both sides. A delta outside -1 to 1 is refused.
"""

from __future__ import annotations

import math
import numbers
import sys
from decimal import Decimal
from typing import TypeVar

__all__ = ["DeltaFilter", "StrikeFilter"]

_Filter = TypeVar("_Filter", bound="_NumericFilter")

# A float's last decimal place; `from_float` keeps a FloatOperation trap quiet.
_LAST_PLACE = Decimal.from_float(math.ulp(0.0)).adjusted()


def _too_far(argument: str, shown: str) -> str:
    """The refusal for a number a float would read as an infinity."""
    return (
        f"{argument} is too far from zero for a float ({shown}): the API would "
        "read it as an infinity"
    )


def _too_close(argument: str, shown: str) -> str:
    """The refusal for a nonzero number a float would read as 0."""
    return (
        f"{argument} is too close to zero for a float ({shown}): the API would "
        "read it as 0"
    )


def _render(
    value: object, argument: str, *, negative_ok: bool, in_a_range: bool = False
) -> str:
    """Render ``value`` as the plain digits the API reads.

    ``argument`` names the value in error messages. A ``Decimal`` or an integer
    keeps its digits, a float is written from its shortest repr, and any other
    real number is converted to a float first. No number is written in exponent
    form. A zero is sent without its sign, and as ``0`` past a float's last
    decimal place.

    Raises ``ValueError`` for a bool, a value that is not a real number, a NaN or
    an infinity, a number a float would read as an infinity or as 0, and a
    negative unless ``negative_ok``; ``in_a_range`` words that refusal for a
    range end.
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
            # Before `Decimal(whole)`, which takes quadratic time in the digits.
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


def _within_one(rendered: str, argument: str) -> str:
    """Return ``rendered``, a delta written by ``_render``, if it is within -1 to 1.

    ``argument`` names the value in the error message. Raises ``ValueError`` if
    it is outside.
    """
    if abs(Decimal(rendered)) > 1:
        raise ValueError(
            f"{argument} is out of range ({rendered}): a delta is between -1 and 1"
        )
    return rendered


class _NumericFilter(str):
    """A ``str`` holding the filter expression, sent to the API as written.

    The classmethods are the checked constructors; calling the class directly
    builds an instance without any check.
    """

    __slots__ = ()

    _WHAT = "value"
    _SINGLE_NEGATIVE_OK = False
    _WITHIN_ONE = False

    @classmethod
    def _checked(
        cls,
        value: object,
        argument: str,
        *,
        negative_ok: bool,
        in_a_range: bool = False,
    ) -> str:
        """Render ``value`` with ``_render`` and, for a delta, ``_within_one``.

        ``argument``, ``negative_ok`` and ``in_a_range`` are passed to
        ``_render``. Returns the text. Raises ``ValueError`` as those two do.
        """
        rendered = _render(
            value, argument, negative_ok=negative_ok, in_a_range=in_a_range
        )
        return _within_one(rendered, argument) if cls._WITHIN_ONE else rendered

    @classmethod
    def _single(cls: type[_Filter], value: object) -> _Filter:
        """Build a one-value filter; ``exact`` and ``nearest`` expose it."""
        return cls(cls._checked(value, cls._WHAT, negative_ok=cls._SINGLE_NEGATIVE_OK))

    @classmethod
    def any_of(cls: type[_Filter], *values: object) -> _Filter:
        """Match any of ``values``, sent as a comma list such as ``250,255``.

        Returns the filter. Raises ``ValueError`` if no value is given or a value
        is refused; a negative is refused for a strike and accepted for a delta.
        """
        if not values:
            raise ValueError(f"any_of needs at least one {cls._WHAT}")
        return cls(
            ",".join(
                cls._checked(value, cls._WHAT, negative_ok=cls._SINGLE_NEGATIVE_OK)
                for value in values
            )
        )

    @classmethod
    def between(cls: type[_Filter], low: object, high: object) -> _Filter:
        """Match ``low`` to ``high`` inclusive, sent as ``low-high``.

        Returns the filter. Raises ``ValueError`` if a bound is refused or
        negative, or if ``low`` is above ``high``.
        """
        rendered_low = cls._checked(low, "low", negative_ok=False, in_a_range=True)
        rendered_high = cls._checked(high, "high", negative_ok=False, in_a_range=True)
        if Decimal(rendered_low) > Decimal(rendered_high):
            raise ValueError(
                f"low must not be above high: {rendered_low}-{rendered_high}"
            )
        return cls(f"{rendered_low}-{rendered_high}")

    @classmethod
    def at_least(cls: type[_Filter], value: object) -> _Filter:
        """Match ``value`` and above, sent as ``>=value``.

        Returns the filter. Raises ``ValueError`` if ``value`` is refused or
        negative.
        """
        return cls(f">={cls._checked(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def at_most(cls: type[_Filter], value: object) -> _Filter:
        """Match ``value`` and below, sent as ``<=value``.

        Returns the filter. Raises ``ValueError`` if ``value`` is refused or
        negative.
        """
        return cls(f"<={cls._checked(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def above(cls: type[_Filter], value: object) -> _Filter:
        """Match strictly above ``value``, sent as ``>value``.

        Returns the filter. Raises ``ValueError`` if ``value`` is refused or
        negative.
        """
        return cls(f">{cls._checked(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def below(cls: type[_Filter], value: object) -> _Filter:
        """Match strictly below ``value``, sent as ``<value``.

        Returns the filter. Raises ``ValueError`` if ``value`` is refused or
        negative.
        """
        return cls(f"<{cls._checked(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def expression(cls: type[_Filter], text: str) -> _Filter:
        """Pass ``text``, an expression written by hand, through as it is.

        For a shape the other constructors do not build. Only its type and that
        it is not blank are checked; the API reads the rest. Returns the filter.
        Raises ``ValueError`` if ``text`` is not a ``str`` or is blank.
        """
        if not isinstance(text, str):
            raise ValueError(f"an expression must be a str, not {type(text).__name__}")
        if not text.strip():
            raise ValueError("an expression cannot be empty")
        return cls(text)


class StrikeFilter(_NumericFilter):
    """The ``strike`` filter of ``options.chain``, a ``str`` holding the expression.

    ``StrikeFilter.between(250, 260)`` is ``"250-260"``. Every constructor but
    ``expression`` takes numbers (``int``, ``float`` or ``Decimal``), sends them
    as plain digits, and raises ``ValueError`` for a bool, a NaN, an infinity, a
    number a float would read as an infinity or as 0, or a negative, which the
    API would answer for its absolute value.
    """

    __slots__ = ()

    _WHAT = "strike"
    _SINGLE_NEGATIVE_OK = False

    @classmethod
    def exact(cls: type[_Filter], value: object) -> _Filter:
        """Match one strike exactly.

        Returns the filter. Raises ``ValueError`` if ``value`` is refused or
        negative.
        """
        return cls._single(value)


class DeltaFilter(_NumericFilter):
    """The ``delta`` filter of ``options.chain``, a ``str`` holding the expression.

    ``DeltaFilter.between(0.3, 0.5)`` is ``"0.3-0.5"``. The API answers a single
    value with the contract whose delta is nearest, per expiration and side, so
    that answer is never empty. It filters on the absolute value and answers both
    sides, so ``0.5`` and ``-0.5`` return the same rows. If any contract in the
    chain has a null delta, the API skips the filter and returns the whole chain;
    with a historical ``date`` it answers ``400``.

    Every constructor but ``expression`` takes numbers (``int``, ``float`` or
    ``Decimal``), sends them as plain digits, and raises ``ValueError`` for a
    bool, a NaN, an infinity, a number a float would read as an infinity or as
    0, or a number outside -1 to 1. A negative is accepted by ``nearest`` and
    ``any_of`` and refused in a range or a bound, where the absolute value would
    change the question.
    """

    __slots__ = ()

    _WHAT = "delta"
    _SINGLE_NEGATIVE_OK = True
    _WITHIN_ONE = True

    @classmethod
    def nearest(cls: type[_Filter], value: object) -> _Filter:
        """Match the delta nearest ``value``, per expiration and side.

        ``value`` may be negative. Returns the filter. Raises ``ValueError`` if
        ``value`` is refused.
        """
        return cls._single(value)


def _render_number(value: object, argument: str) -> str:
    """Render a bare ``strike`` or ``delta`` number the way a filter does.

    Returns the text. Raises ``ValueError`` as ``_render`` does, or for a
    ``delta`` outside -1 to 1; a negative is accepted for ``delta``.
    """
    if argument == "delta":
        return _within_one(_render(value, argument, negative_ok=True), argument)
    return _render(value, argument, negative_ok=False)
