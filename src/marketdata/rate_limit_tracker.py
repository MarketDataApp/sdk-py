"""The client's private, latest-known credit state (SDK requirements §8.3).

It exists for one reason: the pre-flight check that refuses to send a request
when the account has no credits left. It is not a public snapshot (#49): the
numbers a caller can reason about are the request-scoped ones on each result
(:func:`marketdata.get_meta`), and the account balance is one free call away
(``client.utilities.user()``).
"""

from __future__ import annotations

import threading

from marketdata.types import UserRateLimits


class RateLimitTracker:
    """Thread-safe holder of the newest credit state seen in any response.

    Out-of-order updates are discarded, the same rule as sdk-go's tracker: a
    response carrying an older reset window, or a higher remaining count
    within the same window, completed late and would move the state
    backwards.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: UserRateLimits | None = None

    @property
    def state(self) -> UserRateLimits | None:
        with self._lock:
            return self._state

    def update(
        self, rate_limits: UserRateLimits, *, authoritative: bool = False
    ) -> None:
        """Record what an answer said about the account's credits.

        A ``credit_limit`` of zero is not this account's state and is ignored.
        The API answers a missing, malformed or unknown token with demo data
        and a ``0/0`` credit envelope whose reset belongs to another window
        (verified live: a bad token gets ``203`` with ``limit: 0``), so
        recording it would move the pre-flight state to "no credits left" for
        an account that has them, and the ordering rule would then keep the
        real state out until that other window passed.

        ``authoritative`` is for an answer that was asked for precisely to
        learn the balance (``/user/``). It bypasses the ordering rule, which
        otherwise ignores a higher balance in the same window and would leave
        a caller no way to correct a state that is stale rather than late.
        """
        if rate_limits.credit_limit <= 0:
            return
        with self._lock:
            current = self._state
            if current is not None and not authoritative:
                if rate_limits.reset_timestamp < current.reset_timestamp:
                    return
                if (
                    rate_limits.reset_timestamp == current.reset_timestamp
                    and rate_limits.credits_remaining > current.credits_remaining
                ):
                    return
            self._state = rate_limits

    def reset(self, state: UserRateLimits | None = None) -> None:
        """Forget what is known (or replace it), bypassing the ordering rule."""
        with self._lock:
            self._state = state
