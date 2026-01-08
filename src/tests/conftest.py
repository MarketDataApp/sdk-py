import json
import pathlib
import time

import pytest

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
            ],
            "status": [
                "online",
                "online",
                "online",
                "online",
                "online",
                "online",
                "online",
            ],
            "online": [True, True, True, True, True, True, True],
            "uptimePct30d": [100, 100, 100, 100, 100, 100, 100],
            "uptimePct90d": [100, 100, 100, 100, 100, 100, 100],
            "updated": [_time, _time, _time, _time, _time, _time, _time],
        },
        headers=headers,
        status_code=200,
    )

    _client = MarketDataClient(token="test")
    setattr(
        _client,
        "_extract_rate_limits",
        lambda x: UserRateLimits(
            requests_limit=int(headers["x-api-ratelimit-limit"]),
            requests_remaining=int(headers["x-api-ratelimit-remaining"]),
            requests_reset=int(headers["x-api-ratelimit-reset"]),
            requests_consumed=int(headers["x-api-ratelimit-consumed"]),
        ),
    )

    return _client
