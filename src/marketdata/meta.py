"""Request-scoped response metadata (SDK requirements §8.2).

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
every other object (polars frames, single-object models, exceptions) keeps it
in its own ``__dict__``, so a copy, a deep copy or a pickle of it keeps it too.
An object with no ``__dict__`` is remembered by weak reference instead.
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
from marketdata.internal_settings import (
    HEADER_DETECTED_IP,
    HEADER_REQUEST_ID,
    VALID_STATUS_CODES,
    read_header,
)
from marketdata.types import UserRateLimits

# By name, not `get_logger()`: importing the package must not attach a handler.
logger = logging.getLogger("marketdata.logger")

PANDAS_ATTRS_KEY = "marketdata"
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

    On the metadata of a call that raised a ``MarketdataHttpError`` or
    ``RateLimitError``, ``status_code`` and ``request_id`` are those of the
    exception's response (``None`` for a missing or blank ``cf-ray``, where
    the exception says ``"N/A"``), or ``0`` and ``None`` when it carries no
    response. Any other exception follows the rule of a successful call.
    ``responses`` and the credits cover every response the call recorded.

    ``detected_ip`` is the address the API saw the call come from, sent as
    ``X-API-Detected-IP`` on any answer it serves, the empty ``no_data`` one
    included (#44). The API resolves it for an authenticated account that is
    bound to one address, which is the ordinary case; it is ``None`` for an
    account allowed to call from several, for a staff token, for the Sheets
    add-on, and whenever the address could not be resolved. For a call made of
    several requests it comes from the same response as ``status_code`` and
    ``request_id``, falling back to any response that reported one.

    The dataclass is frozen, but that is a shallow guarantee: ``rate_limits``
    is a mutable :class:`UserRateLimits`, so its fields can still be
    reassigned. Treat the whole object as read-only.
    """

    status_code: int
    request_id: str | None
    rate_limits: UserRateLimits | None
    responses: int = 1
    detected_ip: str | None = None

    @classmethod
    def from_response(
        cls, response: Response, rate_limits: UserRateLimits | None
    ) -> ResponseMeta:
        return cls(
            status_code=response.status_code,
            request_id=read_header(response, HEADER_REQUEST_ID),
            rate_limits=rate_limits,
            detected_ip=read_header(response, HEADER_DETECTED_IP),
        )

    @classmethod
    def _merge(
        cls, metas: list[ResponseMeta], *, error: BaseException | None = None
    ) -> ResponseMeta:
        """Merge the metadata of every response behind one call.

        ``error`` is the exception the call raised, if any. Raises
        ``ValueError`` when ``metas`` is empty.
        """
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
        # The address comes from the same response as `status_code` and
        # `request_id`, so the three describe one exchange. Falling back to any
        # response that reported one keeps a call answered from cache, or one
        # whose speaker carried no header, from reading as "no address": every
        # request of a call leaves from the same machine. Scanning the whole
        # list first would make the value depend on which worker thread
        # finished last, which is not something a caller can reason about.
        detected_ip = speaker.detected_ip or next(
            (meta.detected_ip for meta in metas if meta.detected_ip), None
        )
        return cls(
            status_code=speaker.status_code,
            request_id=speaker.request_id,
            rate_limits=rate_limits,
            responses=len(metas),
            detected_ip=detected_ip,
        )

    @classmethod
    def _speaker(
        cls, metas: list[ResponseMeta], error: BaseException | None
    ) -> ResponseMeta:
        """The response that ``status_code`` and ``request_id`` describe.

        The one an SDK HTTP ``error`` carries (a blank one when it carries
        none), else the last one in ``metas`` with a usable status, else the
        last one.
        """
        if isinstance(error, (MarketdataHttpError, RateLimitError)):
            # A non-httpx response falls through: raising here would mask `error`.
            if error.response is None:
                return cls(status_code=0, request_id=None, rate_limits=None)
            if isinstance(error.response, Response):
                return cls.from_response(error.response, None)
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


# Keyed by id(): each entry is dropped when its object is collected, so an id
# that Python hands out again never finds a stale entry.
_registry: dict[int, ResponseMeta] = {}


def _remember(result: Any, meta: ResponseMeta) -> None:
    """Keep the metadata of an object with no ``__dict__`` while it lives.

    Args:
        result: The object.
        meta: The metadata of the call.

    Raises:
        TypeError: When ``result`` cannot be weak-referenced.
    """
    key = id(result)
    weakref.finalize(result, _registry.pop, key, None)
    _registry[key] = meta


def attach_meta(result: Any, meta: ResponseMeta) -> Any:
    """Attach the metadata of a call to what the call returned or raised.

    Args:
        result: The result of the call, or the exception it raised.
        meta: The metadata of the call.

    Returns:
        The object to hand back. A pandas frame carries ``meta`` in
        ``attrs``; a list, a dict or a str comes back as a ``ResultList``,
        ``ResultDict`` or ``CsvPath`` carrying it; any other object carries
        it in its ``__dict__``, or, with none, by weak reference until it is
        collected. ``None``, and an object with neither a ``__dict__`` nor
        weak references, come back as they are and carry nothing; the latter
        is logged at DEBUG.
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
    else:  # polars frames, models, exceptions
        namespace = getattr(result, "__dict__", None)
        if isinstance(namespace, dict):
            namespace[META_ATTRIBUTE] = meta
            return result
        try:
            _remember(result, meta)
        except TypeError:
            logger.debug(
                f"{type(result).__name__} has no __dict__ and cannot be "
                "weak-referenced, so this result carries no response metadata"
            )
        return result
    wrapped.meta = meta
    return wrapped


def get_meta(result: Any) -> ResponseMeta | None:
    """Read the :class:`ResponseMeta` behind a resource call.

    Args:
        result: The result of a successful call, or the exception a failed
            one raised, so the credits a failure consumed are readable too.

    Returns:
        The metadata, or ``None`` when ``result`` carries none.
    """
    if result is None:
        return None
    attrs = getattr(result, "attrs", None)
    if isinstance(attrs, dict):  # pandas
        return attrs.get(PANDAS_ATTRS_KEY)
    if isinstance(result, (ResultList, ResultDict, CsvPath)):
        return result.meta
    namespace = getattr(result, "__dict__", None)
    if isinstance(namespace, dict):
        return namespace.get(META_ATTRIBUTE)
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
