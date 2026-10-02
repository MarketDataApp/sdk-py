"""One request pool per client (SDK requirements §12): at most 50 requests in
flight, shared by every endpoint and every fan-out, and a freed slot goes to the
next request at once."""

import threading
import time

import httpx
import pytest

from marketdata.api_status import API_STATUS_DATA
from marketdata.client import MarketDataClient
from marketdata.exceptions import NetworkError, ServerError
from marketdata.input_types.base import OutputFormat

PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"
FAN_OUT_URL = r".*/v1/(options/quotes|stocks/candles)/.*"
POOL_SIZE = 50
CALLERS = 120
ENOUGH = 1000
WAIT = 10.0
HOLD = 20.0
FINISH = 15.0


class Gate:
    """Holds every request inside the mocked transport and counts them."""

    def __init__(self, answer):
        """Build a gate that lets nothing through until told to.

        Args:
            answer: Builds the response of a request once the gate lets it go.
        """
        self._answer = answer
        self._changed = threading.Condition()
        self._permits = threading.Semaphore(0)
        self.current = 0
        self.started = 0
        self.peak = 0

    def handle(self, request):
        """Count a request in, hold it until it is let go, and count it out.

        Args:
            request: The request the client sent.

        Returns:
            The response built by ``answer``.
        """
        with self._changed:
            self.current += 1
            self.started += 1
            self.peak = max(self.peak, self.current)
            self._changed.notify_all()
        try:
            self._permits.acquire(timeout=HOLD)
        finally:
            with self._changed:
                self.current -= 1
                self._changed.notify_all()
        return self._answer(request)

    def let_go(self, count):
        """Let held requests go.

        Args:
            count: How many requests to let go.
        """
        self._permits.release(count)

    def wait_for(self, condition):
        """Wait until a condition on the gate holds.

        Args:
            condition: Takes the gate and says whether the wait is over.

        Returns:
            Whether the condition held before ``WAIT`` seconds went by.
        """
        with self._changed:
            return self._changed.wait_for(lambda: condition(self), WAIT)

    def settle(self, quiet=0.3):
        """Wait until the number of held requests stops changing.

        Args:
            quiet: How long the number must stay the same, in seconds.

        Returns:
            The number of held requests once it has been steady that long.
        """
        deadline = time.monotonic() + WAIT
        with self._changed:
            while time.monotonic() < deadline:
                before = self.current
                if not self._changed.wait_for(lambda: self.current != before, quiet):
                    break
            return self.current


class Callers:
    """Runs calls in daemon threads and keeps what each returned or raised.

    The threads are daemons so that a call stuck waiting for a slot cannot keep
    the test process alive.
    """

    def __init__(self, calls):
        """Start one thread per call.

        Args:
            calls: The callables to run, each in a thread of its own.
        """
        self.outcomes = [None] * len(calls)
        self._threads = [
            threading.Thread(target=self._run, args=(index, call), daemon=True)
            for index, call in enumerate(calls)
        ]
        for thread in self._threads:
            thread.start()

    def _run(self, index, call):
        """Run one call and keep its outcome.

        Args:
            index: Where the outcome goes in ``outcomes``.
            call: The callable to run.
        """
        try:
            self.outcomes[index] = call()
        except BaseException as exc:
            self.outcomes[index] = exc

    def finish(self):
        """Wait for every call to end.

        Returns:
            What each call returned or raised, in the order they were given.

        Raises:
            AssertionError: A call is still running after ``FINISH`` seconds.
        """
        deadline = time.monotonic() + FINISH
        for thread in self._threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        stuck = sum(thread.is_alive() for thread in self._threads)
        assert not stuck, f"{stuck} calls still waiting after {FINISH} seconds"
        return self.outcomes


def raised(outcomes):
    """Pick the exceptions out of what a set of calls produced.

    Args:
        outcomes: What each call returned or raised.

    Returns:
        The outcomes that are exceptions.
    """
    return [outcome for outcome in outcomes if isinstance(outcome, BaseException)]


def free_slots(client):
    """Count the request slots of a client that are free right now.

    Takes every free slot without waiting and gives them all back, so a leaked
    slot shows as a smaller number instead of a call that never returns.

    Args:
        client: The client whose pool is read.

    Returns:
        The number of free slots.
    """
    taken = 0
    while client._request_slots.acquire(blocking=False):
        taken += 1
    for _ in range(taken):
        client._request_slots.release()
    return taken


def service_unavailable(request):
    """Answer a request with a 503.

    Args:
        request: The request the client sent.

    Returns:
        A 503 response.
    """
    return httpx.Response(503, json={})


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Skip the retry backoff."""
    monkeypatch.setattr("time.sleep", lambda *_: None)


@pytest.fixture(autouse=True)
def _synchronous_status_refresh(monkeypatch):
    """Refresh ``/status/`` inline, so no helper thread holds a slot while a test
    counts them."""
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: API_STATUS_DATA.refresh(c)
    )


def test_120_callers_never_put_more_than_50_requests_in_flight(
    load_json, respx_mock, client
):
    """Callers beyond the 50th wait for a slot instead of reaching the API."""
    body = load_json("stocks_prices_response_200")
    gate = Gate(lambda request: httpx.Response(200, json=body))
    respx_mock.get(PRICES_URL).mock(side_effect=gate.handle)

    callers = Callers(
        [
            lambda: client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
            for _ in range(CALLERS)
        ]
    )
    assert gate.wait_for(lambda g: g.current >= POOL_SIZE), "the pool never filled"
    settled = gate.settle()
    gate.let_go(ENOUGH)
    outcomes = callers.finish()

    assert settled == POOL_SIZE, (
        f"{settled} requests in flight at once, the pool allows {POOL_SIZE}"
    )
    assert gate.peak <= POOL_SIZE
    assert gate.started == CALLERS
    assert not raised(outcomes)


def test_two_fan_outs_started_together_share_the_pool(load_json, respx_mock, client):
    """A ``stocks.candles`` and an ``options.quotes`` running at once draw from
    one budget of 50 requests."""
    quotes = load_json("options_quotes_response_200")
    candles = load_json("stocks_candles_response_200")

    def answer(request):
        """Answer with the body of the endpoint the request is for.

        Args:
            request: The request the client sent.

        Returns:
            A 200 response.
        """
        body = candles if "/stocks/candles/" in request.url.path else quotes
        return httpx.Response(200, json=body)

    gate = Gate(answer)
    respx_mock.get(url__regex=FAN_OUT_URL).mock(side_effect=gate.handle)
    symbols = [f"AAPL250117C{150000 + 500 * i:08d}" for i in range(60)]
    start = threading.Barrier(2, timeout=WAIT)

    def quote_symbols():
        """Quote 60 symbols once both fan-outs are ready."""
        start.wait()
        return client.options.quotes(symbols, output_format=OutputFormat.JSON)

    def fetch_candles():
        """Fetch 60 years of hourly candles, one request per year, once both
        fan-outs are ready."""
        start.wait()
        return client.stocks.candles(
            "AAPL",
            resolution="H",
            from_date="1966-01-01",
            to_date="2026-01-01",
            output_format=OutputFormat.JSON,
        )

    callers = Callers([quote_symbols, fetch_candles])
    assert gate.wait_for(lambda g: g.current >= POOL_SIZE), "the pool never filled"
    settled = gate.settle()
    gate.let_go(ENOUGH)
    outcomes = callers.finish()

    assert settled == POOL_SIZE, (
        f"{settled} requests in flight at once, the pool allows {POOL_SIZE}"
    )
    assert gate.peak <= POOL_SIZE
    assert not raised(outcomes)


def test_a_freed_slot_starts_the_next_request_without_waiting_for_the_others(
    load_json, respx_mock, client
):
    """With 50 requests in flight and one waiting, one completion starts the
    waiting one while the other 49 are still running."""
    body = load_json("stocks_prices_response_200")
    gate = Gate(lambda request: httpx.Response(200, json=body))
    respx_mock.get(PRICES_URL).mock(side_effect=gate.handle)

    callers = Callers(
        [
            lambda: client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
            for _ in range(POOL_SIZE + 1)
        ]
    )
    assert gate.wait_for(lambda g: g.current >= POOL_SIZE), "the pool never filled"
    assert gate.settle() == POOL_SIZE
    gate.let_go(1)

    started = gate.wait_for(lambda g: g.started == POOL_SIZE + 1)
    in_flight = gate.current
    gate.let_go(ENOUGH)
    outcomes = callers.finish()

    assert started, "the waiting request did not start when a slot freed"
    assert in_flight == POOL_SIZE
    assert not raised(outcomes)


@pytest.mark.parametrize(
    ("transport", "ends_in"),
    [
        (httpx.ConnectTimeout("slow"), NetworkError),
        (httpx.ConnectError("refused"), NetworkError),
        (RuntimeError("unexpected"), RuntimeError),
        (service_unavailable, ServerError),
    ],
    ids=["timeout", "connection-error", "unexpected-exception", "5xx-after-retries"],
)
def test_a_failed_request_gives_its_slot_back(transport, ends_in, respx_mock, client):
    """Whatever ends a request, its slot is free before the next one starts.

    Args:
        transport: What the mocked transport does: an exception to raise or a
            function that builds the response.
        ends_in: The exception the call ends in.
    """
    respx_mock.get(PRICES_URL).mock(side_effect=transport)

    for _ in range(POOL_SIZE + 10):
        with pytest.raises(ends_in):
            client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
        assert free_slots(client) == POOL_SIZE


def test_a_retry_holds_no_slot_while_it_backs_off(
    load_json, respx_mock, client, monkeypatch
):
    """Between two attempts of one call, all 50 slots are free."""
    body = load_json("stocks_prices_response_200")
    free_during_backoff = []
    monkeypatch.setattr(
        "time.sleep", lambda *_: free_during_backoff.append(free_slots(client))
    )
    route = respx_mock.get(PRICES_URL).mock(
        side_effect=[httpx.Response(503, json={}), httpx.Response(200, json=body)]
    )

    client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert route.call_count == 2
    assert free_during_backoff == [POOL_SIZE]


def test_each_client_has_its_own_pool(load_json, respx_mock, client):
    """A client with all 50 slots taken leaves another client's slots free."""
    body = load_json("stocks_prices_response_200")
    gate = Gate(lambda request: httpx.Response(200, json=body))
    respx_mock.get(PRICES_URL).mock(side_effect=gate.handle)
    other = MarketDataClient(token="test")

    callers = Callers(
        [
            lambda: client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
            for _ in range(POOL_SIZE)
        ]
    )
    assert gate.wait_for(lambda g: g.current >= POOL_SIZE), "the pool never filled"
    taken = free_slots(client)
    free_on_other = free_slots(other)
    gate.let_go(ENOUGH)
    outcomes = callers.finish()

    assert taken == 0
    assert free_on_other == POOL_SIZE
    assert not raised(outcomes)
