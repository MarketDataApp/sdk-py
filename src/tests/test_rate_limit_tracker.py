"""The private credit tracker behind the pre-flight check (#49)."""

import random
from concurrent.futures import ThreadPoolExecutor

import pytest

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


def test_an_authoritative_update_goes_past_the_ordering_rule():
    """One way past the ordering rule (#104): `client.utilities.user()` is
    asked precisely to learn the balance, so its answer replaces the state
    even when it reports more credits than the tracker holds, which the
    ordering rule reads as a late response. A zero-limit envelope is refused
    before it gets there: the API answers an unknown token with demo data and
    a `0/0` envelope, which would otherwise say this account has nothing."""
    tracker = RateLimitTracker()
    tracker.update(limits(10))

    tracker.update(limits(95), authoritative=True)
    assert tracker.state == limits(95)

    tracker.update(UserRateLimits(0, 0, RESET, 0), authoritative=True)
    assert tracker.state == limits(95)


@pytest.mark.parametrize(
    "state",
    [limits(95), limits(1), limits(50, reset=RESET - 3600), limits(10)],
    ids=["a higher balance", "a lower one", "an older window", "the same state"],
)
def test_an_authoritative_update_leaves_what_reset_leaves(state):
    """The two ways to replace the state are one write in production, and this
    is what a caller can see of that: from the same starting point both end at
    the same state, whatever the ordering rule would have made of it, so a
    change to how a state is replaced cannot land in one path and not the
    other (#104). The zero-limit envelope is the one input where they differ
    on purpose, and the test above is about that."""
    seeded = RateLimitTracker()
    seeded.update(limits(10))
    seeded.update(state, authoritative=True)

    directly = RateLimitTracker()
    directly.update(limits(10))
    directly.reset(state)

    assert seeded.state == directly.state == state


def test_concurrent_updates_end_at_the_lowest_balance():
    tracker = RateLimitTracker()
    balances = list(range(1, 201))
    random.shuffle(balances)

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda remaining: tracker.update(limits(remaining)), balances))

    assert tracker.state.credits_remaining == 1


def test_discard_forgets_the_state_it_was_given():
    tracker = RateLimitTracker()
    state = limits(0)
    tracker.reset(state)

    tracker.discard(state)

    assert tracker.state is None


def test_discard_keeps_a_state_recorded_in_the_meantime():
    """The pre-flight check drops an exhausted state once its window has reset
    (#42). If an answer recorded a fresher state in between, dropping it would
    throw away a real "no credits left" and let the next request out."""
    tracker = RateLimitTracker()
    stale = limits(0)
    tracker.reset(stale)
    fresh = limits(0, reset=RESET + 60)
    tracker.update(fresh)

    tracker.discard(stale)

    assert tracker.state is fresh
