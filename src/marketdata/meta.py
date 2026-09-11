"""Request-scoped response metadata (SDK requirements §8.2, #49).

A resource call returns the data the caller asked for. The metadata of the
HTTP exchange behind it (credits consumed, credits remaining, the request id)
travels with that result instead of living on the shared client, so that
under concurrent calls each result speaks for its own request::

    prices = client.stocks.prices("AAPL")
    meta = marketdata.get_meta(prices)
    meta.rate_limits.credits_consumed

One point attaches (``attach_meta``, called by the resource decorator after
the call completed, retries included) and one point reads (``get_meta``).
The thin containers below keep ``isinstance`` checks against ``list``,
``dict`` and ``str`` working for the INTERNAL, JSON and CSV output formats;
pandas frames carry the metadata in ``DataFrame.attrs["marketdata"]``, and
every other object (polars frames, single-object models) is remembered by
identity without touching its namespace.
"""

from __future__ import annotations

import contextvars
import logging
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from httpx import Response

from marketdata.exceptions import MarketdataHttpError, RateLimitError
from marketdata.internal_settings import VALID_STATUS_CODES
from marketdata.types import UserRateLimits

# The SDK's logger by name, without `get_logger()`: this module is imported
# with the package, and a handler added at import is one more copy of every
# log line (#104). The client installs the handler.
logger = logging.getLogger("marketdata.logger")

PANDAS_ATTRS_KEY = "marketdata"
# Where an exception keeps its metadata. Exceptions cannot go through the
# identity registry below: the built-in ones are not weak-referenceable.
META_ATTRIBUTE = "_marketdata_meta"


@dataclass(frozen=True)
class ResponseMeta:
    """What the API said about one call, next to the data it returned.

    ``rate_limits`` is ``None`` when the response carried no credit headers
    (the ``/status/`` and ``/headers/`` utilities). ``responses`` counts the
    HTTP responses behind the result: one for a plain call, more for a call
    made of several requests (candle chunks, option symbols, retried
    attempts), in which case ``credits_consumed`` is the sum over them,
    ``credit_limit`` and ``reset_time`` those of the newest window,
    ``credits_remaining`` the lowest seen **in that window**, and
    ``status_code`` and ``request_id`` those of the last response that could
    have contributed to the result.

    The balance is scoped to the newest window on purpose: a call whose
    retries cross a reset sees the credits go back up, and the lowest count
    over both windows belongs to a window that has already closed. Pairing it
    with the new window's ``reset_time`` would report a state that never
    existed, the same reason ``RateLimitTracker`` discards an older window.
    ``credits_consumed`` still adds up over every response: those credits were
    really paid for this call, whichever window billed them.

    ``status_code`` and ``request_id`` describe a single response, so they are
    read from the last one whose status is usable, never from a symbol or
    chunk that answered ``no_data`` and was dropped from the merge. That
    matters most for ``request_id``: it is the id to quote in a support
    ticket, and it must name a request that produced part of this result.

    On the metadata of a call that raised, three cases (#104):

    - An SDK HTTP exception (``MarketdataHttpError``, ``RateLimitError``)
      carries the response of the request it is about, the one a support
      ticket is about, and ``status_code`` and ``request_id`` are read from
      it, so they agree with the exception's own.
    - The same exceptions without a response have nothing to describe, and
      report ``0`` and ``None``, as the exception does: the request got no
      answer (a transport failure, the pre-flight refusal), or got one the
      SDK could not read (a body that does not match its
      ``Content-Encoding``; that response is not recorded, so its credits are
      not counted either).
    - Any other exception (a CSV path that already exists, a bare
      ``KeyError`` from an answer the resource could not use) says nothing
      about which request caused it, and the rule of a successful call
      applies: the metadata may then speak for a sibling that answered fine.

    No rule over the responses could pick the failed one: they are listed in
    the order the requests finished, so a sibling that answered later, or an
    attempt that failed and then recovered, would take its place.
    ``responses`` and the credits cover every response the call recorded:
    the failure was billed for them.

    The dataclass is frozen, but that is a shallow guarantee: ``rate_limits``
    is a mutable :class:`UserRateLimits`, so its fields can still be
    reassigned. Treat the whole object as read-only.
    """

    status_code: int
    request_id: str | None
    rate_limits: UserRateLimits | None
    responses: int = 1

    @classmethod
    def from_response(
        cls, response: Response, rate_limits: UserRateLimits | None
    ) -> ResponseMeta:
        return cls(
            status_code=response.status_code,
            request_id=response.headers.get("cf-ray"),
            rate_limits=rate_limits,
        )

    @classmethod
    def merge(
        cls, metas: list[ResponseMeta], *, error: BaseException | None = None
    ) -> ResponseMeta:
        """The metadata of one call, from every response behind it. ``error``
        is the exception the call raised, if it did."""
        if not metas:
            raise ValueError("cannot merge an empty list of ResponseMeta")
        speaker = cls._speaker(metas, error)
        known = [meta.rate_limits for meta in metas if meta.rate_limits is not None]
        rate_limits = None
        if known:
            newest = max(known, key=lambda limits: limits.reset_timestamp)
            current = [
                limits
                for limits in known
                if limits.reset_timestamp == newest.reset_timestamp
            ]
            rate_limits = UserRateLimits(
                credit_limit=newest.credit_limit,
                credits_remaining=min(limits.credits_remaining for limits in current),
                reset_time=newest.reset_time,
                credits_consumed=sum(limits.credits_consumed for limits in known),
            )
        return cls(
            status_code=speaker.status_code,
            request_id=speaker.request_id,
            rate_limits=rate_limits,
            responses=len(metas),
        )

    @classmethod
    def _speaker(
        cls, metas: list[ResponseMeta], error: BaseException | None
    ) -> ResponseMeta:
        """The one response that ``status_code`` and ``request_id`` describe."""
        if isinstance(error, (MarketdataHttpError, RateLimitError)):
            # The exception names the request that failed (#104). Only that
            # response's own fields are read from it; the credits come from
            # the whole list. Anything but an httpx response there (a caller's
            # subclass, a test double) falls through to the rule below rather
            # than raise inside the decorator's `except` and replace the
            # caller's exception.
            if error.response is None:
                return cls(status_code=0, request_id=None, rate_limits=None)
            if isinstance(error.response, Response):
                return cls.from_response(error.response, None)
        # The last response that could have contributed to the result: the
        # same `VALID_STATUS_CODES` the fan-outs use to build their `usable`
        # list. Otherwise a symbol answering 404 `no_data` (recorded, then
        # dropped from the merge) could label a successful call as a 404 and
        # hand support the request id of the one response that returned
        # nothing. With no usable response the last one is the honest answer.
        usable = [meta for meta in metas if meta.status_code in VALID_STATUS_CODES]
        return usable[-1] if usable else metas[-1]


class ResultList(list):
    """A list result (records) carrying the response metadata on ``meta``."""

    meta: ResponseMeta | None = None


class ResultDict(dict):
    """A JSON result carrying the response metadata on ``meta``."""

    meta: ResponseMeta | None = None


class CsvPath(str):
    """A CSV output path carrying the response metadata on ``meta``."""

    meta: ResponseMeta | None = None


# Metadata of the objects that are neither wrapped nor pandas frames (polars
# frames, single-object models), keyed by identity and dropped with the object,
# so a model's own namespace is never touched (`vars(model)` stays the model).
_registry: dict[int, ResponseMeta] = {}


def _remember(obj: Any, meta: ResponseMeta) -> None:
    key = id(obj)
    try:
        weakref.finalize(obj, _registry.pop, key, None)
    except TypeError:
        # Nothing safe to hang it on. Exceptions took the attribute path
        # above, so what reaches this is an exotic result type; say so at
        # DEBUG rather than dropping the metadata in silence.
        logger.debug(
            f"{type(obj).__name__} cannot be weak-referenced, so this result "
            "carries no response metadata"
        )
        return
    _registry[key] = meta


def attach_meta(result: Any, meta: ResponseMeta) -> Any:
    """Attach ``meta`` to ``result`` and return the object to hand back.

    ``None`` (a single-object endpoint with no data) cannot carry anything and
    is returned as is. An exception carries the metadata as an attribute:
    that is how a failed call still reports what it was billed, and the
    identity path cannot do it, because a built-in exception (the
    ``FileExistsError`` of an existing CSV path, a decoder ``KeyError``)
    cannot be weak-referenced.
    """
    if result is None:
        return None
    if isinstance(result, BaseException):
        result.__dict__[META_ATTRIBUTE] = meta
        return result
    attrs = getattr(result, "attrs", None)
    if isinstance(attrs, dict):  # pandas
        attrs[PANDAS_ATTRS_KEY] = meta
        return result
    if isinstance(result, list):
        wrapped: Any = ResultList(result)
    elif isinstance(result, dict):
        wrapped = ResultDict(result)
    elif isinstance(result, str):
        wrapped = CsvPath(result)
    else:  # polars frames, dataclass models
        _remember(result, meta)
        return result
    wrapped.meta = meta
    return wrapped


def get_meta(result: Any) -> ResponseMeta | None:
    """The :class:`ResponseMeta` behind a resource call, if any.

    Takes the result of a successful call or the exception a failed one
    raised, so the credits a failure consumed are readable too.
    """
    if result is None:
        return None
    if isinstance(result, BaseException):
        return result.__dict__.get(META_ATTRIBUTE)
    attrs = getattr(result, "attrs", None)
    if isinstance(attrs, dict):  # pandas
        return attrs.get(PANDAS_ATTRS_KEY)
    if isinstance(result, (ResultList, ResultDict, CsvPath)):
        return result.meta
    return _registry.get(id(result))


# ---------------------------------------------------------------- collection
#
# `_make_request` records every response it handles into the scope opened by
# the resource decorator for the current call. A ContextVar (not a thread
# local) so the fan-out resources can hand the scope to their worker threads
# with `contextvars.copy_context().run`.

_scope: contextvars.ContextVar[list[ResponseMeta] | None] = contextvars.ContextVar(
    "marketdata_response_scope", default=None
)


@contextmanager
def collect_metas() -> Iterator[list[ResponseMeta]]:
    metas: list[ResponseMeta] = []
    token = _scope.set(metas)
    try:
        yield metas
    finally:
        _scope.reset(token)


def record_meta(meta: ResponseMeta) -> None:
    metas = _scope.get()
    if metas is not None:
        metas.append(meta)
