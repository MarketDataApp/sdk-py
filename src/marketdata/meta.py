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
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from httpx import Response

from marketdata.types import UserRateLimits

PANDAS_ATTRS_KEY = "marketdata"


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
    ``status_code`` and ``request_id`` those of the last response.

    The balance is scoped to the newest window on purpose: a call whose
    retries cross a reset sees the credits go back up, and the lowest count
    over both windows belongs to a window that has already closed. Pairing it
    with the new window's ``reset_time`` would report a state that never
    existed, the same reason ``RateLimitTracker`` discards an older window.
    ``credits_consumed`` still adds up over every response: those credits were
    really paid for this call, whichever window billed them.
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
    def merge(cls, metas: list[ResponseMeta]) -> ResponseMeta:
        last = metas[-1]
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
            status_code=last.status_code,
            request_id=last.request_id,
            rate_limits=rate_limits,
            responses=len(metas),
        )


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
    except TypeError:  # not weak-referenceable: nothing safe to hang it on
        return
    _registry[key] = meta


def attach_meta(result: Any, meta: ResponseMeta) -> Any:
    """Attach ``meta`` to ``result`` and return the object to hand back.

    ``None`` (a single-object endpoint with no data) cannot carry anything and
    is returned as is. An exception takes the identity path like any other
    object, which is how a failed call still reports what it was billed.
    """
    if result is None:
        return None
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
