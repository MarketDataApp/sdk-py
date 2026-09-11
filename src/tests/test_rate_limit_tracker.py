"""The private credit tracker behind the pre-flight check (#49)."""

import random
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from marketdata.rate_limit_tracker import RateLimitTracker
from marketdata.types import UserRateLimits

RESET = 1734567890


def limits(remaining, reset=RESET, consumed=1):
    return UserRateLimits(
        credit_limit=100,
        credits_remaining=remaining,
        reset_time=reset,
        credits_consumed=consumed,
    )


def test_starts_unknown_and_takes_the_first_state():
    tracker = RateLimitTracker()
    assert tracker.state is None

    tracker.update(limits(99))

    assert tracker.state == limits(99)


def test_a_lower_balance_in_the_same_window_wins():
    tracker = RateLimitTracker()
    tracker.update(limits(99))

    tracker.update(limits(97))
    tracker.update(limits(97))  # equal balance: accepted, a fresher report

    assert tracker.state.credits_remaining == 97


def test_a_higher_balance_in_the_same_window_is_a_late_response():
    tracker = RateLimitTracker()
    tracker.update(limits(90))

    tracker.update(limits(95))

    assert tracker.state.credits_remaining == 90


def test_an_older_window_is_ignored_and_a_newer_one_replaces():
    tracker = RateLimitTracker()
    tracker.update(limits(50, reset=RESET))

    tracker.update(limits(10, reset=RESET - 3600))
    assert tracker.state.credits_remaining == 50

    tracker.update(limits(100, reset=RESET + 3600))
    assert tracker.state.credits_remaining == 100


def test_reset_bypasses_the_ordering_rule():
    tracker = RateLimitTracker()
    tracker.update(limits(10))

    tracker.reset(limits(95))
    assert tracker.state.credits_remaining == 95

    tracker.reset()
    assert tracker.state is None


def test_an_authoritative_update_writes_through_reset():
    """One way past the ordering rule (#104): an authoritative update applies
    the zero-limit guard and then writes through `reset`, so a change to how a
    state is replaced cannot land in one path and not the other, and the tests
    that seed the tracker through `reset` exercise the write production uses."""
    tracker = RateLimitTracker()
    tracker.update(limits(10))

    with patch.object(tracker, "reset", wraps=tracker.reset) as reset:
        tracker.update(limits(95), authoritative=True)
        tracker.update(UserRateLimits(0, 0, RESET, 0), authoritative=True)

    reset.assert_called_once_with(limits(95))
    assert tracker.state == limits(95)


def test_concurrent_updates_end_at_the_lowest_balance():
    tracker = RateLimitTracker()
    balances = list(range(1, 201))
    random.shuffle(balances)

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda remaining: tracker.update(limits(remaining)), balances))

    assert tracker.state.credits_remaining == 1
