"""Live integration suite: every test here talks to api.marketdata.app.

The suite is excluded from the default ``pytest`` run by the ``-m "not
integration"`` in ``pyproject.toml``. Run it explicitly:

    MARKETDATA_TOKEN=... uv run pytest src/tests/integration -m integration

A missing token FAILS the suite, it never skips it (SDK requirements sections 13 and
17.3): a suite that skips when unauthenticated reports success while testing
nothing. Symbols are the free-trial ones (AAPL, VFINX) so a run costs no API
credits; every endpoint is asserted on the shape of the decoded response, not
merely on a 2xx.
"""

import os
import pathlib

import pytest

from marketdata import MarketDataClient

INTEGRATION_DIR = pathlib.Path(__file__).parent

MISSING_TOKEN_MESSAGE = (
    "MARKETDATA_TOKEN is not set. The live integration suite refuses to run "
    "without a token instead of skipping (SDK requirements, section 13): a green run "
    "that made no request would mean nothing. Export MARKETDATA_TOKEN and rerun."
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # Every test under this directory is a live test, whether or not its author
    # remembered to mark it, so the marker is applied here in one place.
    for item in items:
        if INTEGRATION_DIR in pathlib.Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def live_token() -> str:
    token = os.environ.get("MARKETDATA_TOKEN", "").strip()
    if not token:
        pytest.fail(MISSING_TOKEN_MESSAGE, pytrace=False)
    return token


@pytest.fixture(scope="session")
def live_client(live_token: str) -> MarketDataClient:
    # One client per session: construction already makes a live /user/ call to
    # seed the rate limits, so this is also the first live assertion.
    client = MarketDataClient(token=live_token)
    assert client.rate_limits is not None, "/user/ did not return rate-limit headers"
    assert client.rate_limits.requests_limit > 0
    return client
