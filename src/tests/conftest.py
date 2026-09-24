import json
import pathlib
import time

import httpx
import pytest

from marketdata.api_status import API_STATUS_DATA
from marketdata.client import MarketDataClient
from marketdata.types import UserRateLimits

DATA_DIR = pathlib.Path(__file__).parent / "data"


@pytest.fixture
def load_json():
    def _loader(name) -> dict:
        filepath = DATA_DIR / f"{name}.json"
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    return _loader


@pytest.fixture(autouse=True)
def chdir(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def _reset_api_status_data():
    API_STATUS_DATA.__init__()
    yield
    if API_STATUS_DATA._refresh_thread is not None:
        API_STATUS_DATA._refresh_thread.join(timeout=2)
    API_STATUS_DATA.__init__()


def use_real_header_extraction(client):
    """Undo the instance-level patch of ``_extract_rate_limits`` below, so a
    test reads the credit headers its mocked answers really carry."""
    client.__dict__.pop("_extract_rate_limits", None)
    return client


def load_api_status(client) -> None:
    """Load the ``/status/`` answer the test mocked into the status cache.

    An empty cache answers "unknown" to the first failure of a call, so a
    mocked outage is only seen once it is loaded.
    """
    API_STATUS_DATA.refresh(client)


def assert_failed_answer(error, status_code: int, url: str, message: str) -> None:
    """Check that an SDK exception names the answer that failed.

    Args:
        error: The exception the call raised.
        status_code: The status of the failed answer, ``0`` when there was none.
        url: The URL of the failed request, without its query.
        message: The API's ``errmsg``, or the body when it carries none.
    """
    assert error.status_code == status_code
    assert error.request_url.partition("?")[0] == str(httpx.URL(url))
    assert error.message == message


@pytest.fixture
def client(respx_mock):

    headers = {
        "x-api-ratelimit-limit": "100",
        "x-api-ratelimit-remaining": "99",
        "x-api-ratelimit-reset": "60",
        "x-api-ratelimit-consumed": "1",
    }

    respx_mock.get("https://api.marketdata.app/user/").respond(
        json={},
        headers=headers,
        status_code=200,
    )

    _time = time.time()
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json={
            "service": [
                "/v1/markets/status/",
                "/v1/options/chain/",
                "/v1/options/expirations/",
                "/v1/options/quotes/",
                "/v1/options/strikes/",
                "/v1/stocks/candles/",
                "/v1/stocks/bulkquotes/",
                "/v1/stocks/quotes/",
            ],
            "status": ["online"] * 8,
            "online": [True] * 8,
            "uptimePct30d": [100] * 8,
            "uptimePct90d": [100] * 8,
            "updated": [_time] * 8,
        },
        headers=headers,
        status_code=200,
    )

    _client = MarketDataClient(token="test")
    setattr(
        _client,
        "_extract_rate_limits",
        lambda x: UserRateLimits(
            credit_limit=int(headers["x-api-ratelimit-limit"]),
            credits_remaining=int(headers["x-api-ratelimit-remaining"]),
            reset_time=int(headers["x-api-ratelimit-reset"]),
            credits_consumed=int(headers["x-api-ratelimit-consumed"]),
        ),
    )

    return _client
