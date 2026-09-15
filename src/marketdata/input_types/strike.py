"""The strike filter of ``options.chain`` (#101).

The API reads ``strike`` as a small expression language, not as one number:
``250`` is an exact strike, ``250,255`` a set, ``250-260`` an inclusive range,
and ``>=250`` a one-sided bound (``common/util/input_validation_helper.py``,
``parse_numeric_query``). Written as a string that grammar is easy to get
wrong and invisible to a type checker, so the shapes have constructors, the
way sdk-go and sdk-csharp give them.

``StrikeFilter`` is a ``str``: it carries the expression it renders and needs
no conversion anywhere between here and the query string. A plain number and a
plain string still work, so nothing that used to compile stops compiling.
"""

from __future__ import annotations

import numbers
from decimal import Decimal

__all__ = ["StrikeFilter", "render_strike"]


def render_strike(price: object, argument: str = "price") -> str:
    """One strike price as the digits the API should read.

    A ``Decimal`` renders through ``str`` and a float through its shortest
    repr, so ``65.1`` goes out as ``65.1`` rather than as the binary expansion
    behind it. An ``int`` is exact as it is.
    """
    if isinstance(price, bool):
        raise TypeError(f"{argument} cannot be a bool: {price!r}")
    if isinstance(price, Decimal):
        if not price.is_finite():
            raise ValueError(f"{argument} must be a finite amount, not {price!r}")
        return str(price)
    if isinstance(price, numbers.Integral):
        return str(int(price))
    if isinstance(price, numbers.Real):
        value = float(price)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{argument} must be a finite amount, not {price!r}")
        return repr(value)
    raise TypeError(f"{argument} must be a number, not {type(price).__name__}")


class StrikeFilter(str):
    """A ``strike`` filter, rendered as the expression the API reads.

    It is a ``str``, so it travels to the query string with no handling of its
    own and a caller can print or compare it like any other string::

        chain = client.options.chain("AAPL", strike=StrikeFilter.between(250, 260))
        str(StrikeFilter.at_least(250))     # '>=250'
    """

    __slots__ = ()

    @classmethod
    def exact(cls, price: object) -> StrikeFilter:
        """One strike price: ``strike=250``."""
        return cls(render_strike(price))

    @classmethod
    def any_of(cls, *prices: object) -> StrikeFilter:
        """A set of exact strikes: ``strike=250,255``.

        Both sides come back at each one unless ``side`` narrows it, which is
        how a spread is priced in one request instead of one call per leg.
        """
        if not prices:
            raise ValueError("any_of needs at least one strike price")
        return cls(",".join(render_strike(price) for price in prices))

    @classmethod
    def between(cls, low: object, high: object) -> StrikeFilter:
        """An inclusive range: ``strike=250-260``."""
        rendered_low = render_strike(low, "low")
        rendered_high = render_strike(high, "high")
        if Decimal(rendered_low) > Decimal(rendered_high):
            raise ValueError(
                f"low must not be above high: {rendered_low}-{rendered_high}"
            )
        return cls(f"{rendered_low}-{rendered_high}")

    @classmethod
    def at_least(cls, price: object) -> StrikeFilter:
        """Strikes at or above a price: ``strike=>=250``."""
        return cls(f">={render_strike(price)}")

    @classmethod
    def at_most(cls, price: object) -> StrikeFilter:
        """Strikes at or below a price: ``strike=<=250``."""
        return cls(f"<={render_strike(price)}")

    @classmethod
    def above(cls, price: object) -> StrikeFilter:
        """Strikes strictly above a price: ``strike=>250``."""
        return cls(f">{render_strike(price)}")

    @classmethod
    def below(cls, price: object) -> StrikeFilter:
        """Strikes strictly below a price: ``strike=<250``."""
        return cls(f"<{render_strike(price)}")

    @classmethod
    def expression(cls, text: str) -> StrikeFilter:
        """An expression written by hand, passed through as it is.

        The escape hatch for a shape the constructors above do not name, the
        way ``StrikeExpr`` is in sdk-go. Nothing is checked here beyond it
        being a non-empty string: the API decides.
        """
        if not isinstance(text, str):
            raise TypeError(f"an expression must be a str, not {type(text).__name__}")
        if not text.strip():
            raise ValueError("an expression cannot be empty")
        return cls(text)
