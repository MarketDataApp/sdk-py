"""The numeric filters of ``options.chain``: ``strike`` and ``delta`` (#101).

The API reads both as a small expression language rather than as one number
(``common/util/input_validation_helper.py``, ``parse_numeric_query`` and
``parse_input_expression``): ``250`` is one value, ``250,255`` a set,
``250-260`` an inclusive range, and ``>=250`` a one-sided bound. Written as a
string that grammar is easy to get wrong and invisible to a type checker, so
each shape has a constructor, the way sdk-go gives them. sdk-csharp names
three of these shapes and has no filter for ``delta`` at all.

Two of its rules are sharp edges, both measured against production on
2026-09-15:

- ``parse_input`` is ``abs(float(value))``, so a minus sign is dropped without
  a word. ``strike=-250`` answers with the strikes at ``250``.
- ``parse_input_expression`` skips the range branch when the text opens with a
  minus, so ``-0.5-0.5`` reaches ``float()`` whole and the call fails with a
  ``400``.

Where a negative changes what the caller asked for, it is refused here with a
message rather than sent. ``delta`` is the exception the API documents: it
filters on the absolute value and answers both sides, so ``0.5`` and ``-0.5``
return the same rows, verified, and both are accepted for an exact value.
"""

from __future__ import annotations

import numbers
from decimal import Decimal

__all__ = ["DeltaFilter", "StrikeFilter"]


def _render(
    value: object, argument: str, *, negative_ok: bool, in_a_range: bool = False
) -> str:
    """One number as the digits the API should read.

    A ``Decimal`` renders through ``str`` and every other number through
    ``str`` as well, which for a float is its shortest form. A positive
    exponent travels fine: ``Decimal("250.00").normalize()`` is
    ``Decimal("2.5E+2")``, and the API answers ``250`` for it, measured. What
    cannot travel is a minus anywhere but the front, since the API reads the
    text around one as a range: ``1e-05`` becomes ``1e`` to ``05``.
    """
    if isinstance(value, bool):
        raise ValueError(f"{argument} cannot be a bool: {value!r}")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{argument} must be a finite number, not {value!r}")
        rendered = str(value)
    elif isinstance(value, numbers.Integral):
        rendered = str(int(value))
    elif isinstance(value, numbers.Real):
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            raise ValueError(f"{argument} must be a finite number, not {value!r}")
        rendered = str(number)
    else:
        raise ValueError(f"{argument} must be a number, not {type(value).__name__}")

    if Decimal(rendered) == 0:
        # `-0.0` is zero and the API answers `0` for it, so the sign goes
        # rather than the value being refused for a minus nobody wrote.
        rendered = rendered.lstrip("-")
    if "-" in rendered[1:]:
        halves = rendered[1:].split("-")
        raise ValueError(
            f"{argument} cannot carry a minus inside it ({rendered}): the API "
            "reads the text around one as a range, so this would be read as "
            f"{halves[0]!r} to {halves[1]!r}. Round it, or write the "
            "expression by hand"
        )
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
    _EXACT_NEGATIVE_OK = False

    @classmethod
    def exact(cls, value: object) -> _NumericFilter:
        """One value."""
        return cls(_render(value, cls._WHAT, negative_ok=cls._EXACT_NEGATIVE_OK))

    @classmethod
    def any_of(cls, *values: object) -> _NumericFilter:
        """A set of exact values, sent as a comma list.

        Both sides come back at each one unless ``side`` narrows it, which is
        how a spread is priced in one request instead of one call per leg.
        """
        if not values:
            raise ValueError(f"any_of needs at least one {cls._WHAT}")
        return cls(
            ",".join(
                _render(value, cls._WHAT, negative_ok=cls._EXACT_NEGATIVE_OK)
                for value in values
            )
        )

    @classmethod
    def between(cls, low: object, high: object) -> _NumericFilter:
        """An inclusive range, sent as ``low-high``."""
        rendered_low = _render(low, "low", negative_ok=False, in_a_range=True)
        rendered_high = _render(high, "high", negative_ok=False, in_a_range=True)
        if Decimal(rendered_low) > Decimal(rendered_high):
            raise ValueError(
                f"low must not be above high: {rendered_low}-{rendered_high}"
            )
        return cls(f"{rendered_low}-{rendered_high}")

    @classmethod
    def at_least(cls, value: object) -> _NumericFilter:
        """At or above a value, sent as ``>=value``."""
        return cls(f">={_render(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def at_most(cls, value: object) -> _NumericFilter:
        """At or below a value, sent as ``<=value``."""
        return cls(f"<={_render(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def above(cls, value: object) -> _NumericFilter:
        """Strictly above a value, sent as ``>value``."""
        return cls(f">{_render(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def below(cls, value: object) -> _NumericFilter:
        """Strictly below a value, sent as ``<value``."""
        return cls(f"<{_render(value, cls._WHAT, negative_ok=False)}")

    @classmethod
    def expression(cls, text: str) -> _NumericFilter:
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
    _EXACT_NEGATIVE_OK = False


class DeltaFilter(_NumericFilter):
    """The ``delta`` filter of ``options.chain``.

    Three things the API does with this parameter are worth knowing before
    the constructors make sense.

    It matches the **nearest** delta rather than the one asked for: per
    expiration and side it sorts by distance and takes the closest, so
    ``exact(0.5)`` answered ``[0.5266, -0.4729]`` when it was measured, and
    never answers with nothing. ``exact`` names the shape of the expression,
    not the precision of the match.

    It filters on the **absolute value** and answers both sides, so ``0.5``
    and ``-0.5`` return the same rows, measured. Both are accepted for an
    exact value and for a set.

    A value above 1 is read as a percentage: ``exact(30)`` means ``0.30``.

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
    _EXACT_NEGATIVE_OK = True


def render_number(value: object, argument: str) -> str:
    """A bare number for one of these parameters, as its digits.

    The field validators use it so a caller who passes a plain number gets the
    same reading, and the same refusals, as one who builds a filter.
    """
    return _render(value, argument, negative_ok=argument == "delta")
