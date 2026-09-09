"""Request-scoped response metadata (#49, SDK requirements §8.2): every
result carries the credits its own request cost, also under concurrency."""

import gc
import pathlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from unittest.mock import patch

import httpx
import pytest

import marketdata
from marketdata.api_status import API_STATUS_DATA
from marketdata.input_types.base import OutputFormat
from marketdata.meta import (
    CsvPath,
    ResponseMeta,
    ResultDict,
    ResultList,
    _registry,
    attach_meta,
    get_meta,
)
from marketdata.types import UserRateLimits

PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"
EXPIRATIONS_URL = "https://api.marketdata.app/v1/options/expirations/AAPL/"
CANDLES_URL = "https://api.marketdata.app/v1/stocks/candles/H/AAPL/"
STATUS_URL = "https://api.marketdata.app/status/"
RESET = 1734567890
NO_DATA = {"s": "no_data"}


def prices_body(symbol="AAPL"):
    return {
        "s": "ok",
        "symbol": [symbol],
        "mid": [190.5],
        "change": [1.5],
        "changepct": [0.008],
        "updated": [RESET],
    }


def credit_headers(consumed, remaining, limit=100, reset=RESET, request_id="abc-EZE"):
    return {
        "x-api-ratelimit-limit": str(limit),
        "x-api-ratelimit-remaining": str(remaining),
        "x-api-ratelimit-reset": str(reset),
        "x-api-ratelimit-consumed": str(consumed),
        "cf-ray": request_id,
    }


@pytest.fixture
def real_headers(client):
    """The conftest client patches header extraction at the instance level and
    seeds the tracker from its own headers; these tests read real headers and
    start from a known balance in the same reset window."""
    client.__dict__.pop("_extract_rate_limits", None)
    client._rate_limits.reset(
        UserRateLimits(
            credit_limit=100,
            credits_remaining=100,
            reset_time=RESET,
            credits_consumed=0,
        )
    )
    return client


def test_every_output_format_carries_the_response_meta(
    respx_mock, real_headers, tmp_path
):
    client = real_headers
    respx_mock.get(PRICES_URL).respond(
        json=prices_body(), status_code=200, headers=credit_headers(3, 97)
    )

    records = client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)
    body = client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    path = client.stocks.prices(
        "AAPL", output_format=OutputFormat.CSV, filename=str(tmp_path / "p.csv")
    )

    # The containers still are what callers expect them to be.
    assert isinstance(records, list) and type(records) is ResultList
    assert isinstance(body, dict) and type(body) is ResultDict
    assert isinstance(path, str) and type(path) is CsvPath
    assert pathlib.Path(path).exists()
    expected = ResponseMeta(
        status_code=200,
        request_id="abc-EZE",
        rate_limits=UserRateLimits(
            credit_limit=100, credits_remaining=97, reset_time=RESET, credits_consumed=3
        ),
    )
    for result in (records, body, path):
        assert get_meta(result) == expected
        assert result.meta == expected


@pytest.mark.parametrize("handler", ["pandas", "polars"])
def test_dataframes_carry_the_response_meta(respx_mock, real_headers, handler):
    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", [handler]):
        respx_mock.get(PRICES_URL).respond(
            json=prices_body(), status_code=200, headers=credit_headers(2, 98)
        )

        df = real_headers.stocks.prices("AAPL", output_format=OutputFormat.DATAFRAME)

    assert get_meta(df).rate_limits.credits_consumed == 2
    assert len(df) == 1


def test_single_object_results_carry_the_response_meta(respx_mock, real_headers):
    respx_mock.get(EXPIRATIONS_URL).respond(
        json={"s": "ok", "expirations": ["2025-01-17"], "updated": RESET},
        status_code=200,
        headers=credit_headers(1, 99, request_id="single-1"),
    )

    expirations = real_headers.options.expirations(
        "AAPL", output_format=OutputFormat.INTERNAL
    )

    assert len(expirations.expirations) == 1
    assert get_meta(expirations).request_id == "single-1"
    # The model's own namespace is untouched: vars(model) stays the model.
    assert "meta" not in vars(expirations)


def test_no_data_results_carry_the_meta_when_they_can(respx_mock, real_headers):
    respx_mock.get(PRICES_URL).respond(
        json=NO_DATA, status_code=404, headers=credit_headers(0, 100)
    )
    respx_mock.get(EXPIRATIONS_URL).respond(
        json=NO_DATA, status_code=404, headers=credit_headers(0, 100)
    )

    empty = real_headers.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)
    nothing = real_headers.options.expirations(
        "AAPL", output_format=OutputFormat.INTERNAL
    )

    assert empty == []
    assert get_meta(empty).status_code == 404
    assert get_meta(empty).rate_limits.credits_consumed == 0
    # None cannot carry anything: documented limitation.
    assert nothing is None
    assert get_meta(nothing) is None


def test_a_failed_call_reports_the_credits_it_was_billed(respx_mock, real_headers):
    """A failure is billed like any other answer, so the exception carries the
    same metadata a result would: `get_meta(exc)` says what the call cost."""
    respx_mock.get(PRICES_URL).respond(
        json={"s": "error", "errmsg": "Symbol not found."},
        status_code=404,
        headers=credit_headers(10, 90, request_id="failed-1"),
    )

    with pytest.raises(marketdata.NotFoundError) as exc_info:
        real_headers.stocks.prices("ZZZZ", output_format=OutputFormat.INTERNAL)

    meta = get_meta(exc_info.value)
    assert meta is not None
    assert meta.status_code == 404
    assert meta.request_id == "failed-1"
    assert meta.rate_limits.credits_consumed == 10
    assert meta.rate_limits.credits_remaining == 90


def test_a_failure_with_no_response_carries_no_meta(client):
    """A call that never reached the API (the pre-flight check) has nothing to
    report, and nothing is invented for it."""
    client._rate_limits.reset(
        UserRateLimits(
            credit_limit=100, credits_remaining=0, reset_time=RESET, credits_consumed=0
        )
    )

    with pytest.raises(marketdata.RateLimitError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)

    assert get_meta(exc_info.value) is None


def test_concurrent_calls_keep_their_own_consumed_credits(respx_mock, real_headers):
    """The issue's test: parallel calls with distinct consumed values, each
    result carries its own, and no shared state is read for attribution."""
    client = real_headers
    costs = {f"SYM{i}": i + 1 for i in range(8)}
    client._rate_limits.reset(
        UserRateLimits(
            credit_limit=1000,
            credits_remaining=1000,
            reset_time=RESET,
            credits_consumed=0,
        )
    )

    def answer(request):
        symbol = request.url.params["symbols"]
        return httpx.Response(
            200,
            json=prices_body(symbol),
            headers=credit_headers(costs[symbol], 1000 - costs[symbol], limit=1000),
        )

    respx_mock.get(PRICES_URL).mock(side_effect=answer)

    with ThreadPoolExecutor(max_workers=len(costs)) as pool:
        results = dict(
            zip(
                costs,
                pool.map(
                    lambda s: client.stocks.prices(
                        s, output_format=OutputFormat.INTERNAL
                    ),
                    costs,
                ),
            )
        )

    for symbol, cost in costs.items():
        meta = get_meta(results[symbol])
        assert meta.rate_limits.credits_consumed == cost
        assert meta.rate_limits.credits_remaining == 1000 - cost
        assert results[symbol][0].symbol == symbol
    # The private tracker ends at the lowest balance whatever the completion
    # order, which is all the pre-flight check needs.
    assert client._rate_limits.state.credits_remaining == 1000 - max(costs.values())


def test_fan_out_meta_adds_up_the_chunks(load_json, respx_mock, real_headers):
    chunk = load_json("stocks_candles_response_200")
    respx_mock.get(CANDLES_URL).mock(
        side_effect=[
            httpx.Response(
                200, json=chunk, headers=credit_headers(5, 95, request_id="chunk-1")
            ),
            httpx.Response(
                200, json=chunk, headers=credit_headers(7, 88, request_id="chunk-2")
            ),
        ]
    )

    candles = real_headers.stocks.candles(
        "AAPL",
        resolution="H",
        from_date="2023-01-01",
        to_date="2024-06-01",
        output_format=OutputFormat.INTERNAL,
    )

    meta = get_meta(candles)
    assert meta.responses == 2
    assert meta.rate_limits.credits_consumed == 12
    assert meta.rate_limits.credits_remaining == 88
    assert meta.request_id in {"chunk-1", "chunk-2"}
    assert len(candles) == 2 * len(chunk["t"])


def test_retried_attempts_count_and_the_status_refresh_does_not(
    respx_mock, real_headers, monkeypatch
):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    monkeypatch.setattr(
        API_STATUS_DATA, "_trigger_async_refresh", lambda c: API_STATUS_DATA.refresh(c)
    )
    respx_mock.get(PRICES_URL).mock(
        side_effect=[
            httpx.Response(
                503, json={}, headers=credit_headers(0, 99, request_id="try-1")
            ),
            httpx.Response(
                200,
                json=prices_body(),
                headers=credit_headers(1, 98, request_id="try-2"),
            ),
        ]
    )

    prices = real_headers.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)

    status_calls = [c for c in respx_mock.calls if c.request.url.path == "/status/"]
    assert status_calls, "the retry did consult the status cache"
    meta = get_meta(prices)
    assert meta.responses == 2
    assert meta.status_code == 200
    assert meta.request_id == "try-2"
    assert meta.rate_limits.credits_consumed == 1
    assert meta.rate_limits.credits_remaining == 98


def test_utilities_without_credit_headers_still_carry_the_meta(
    load_json, respx_mock, client
):
    respx_mock.get(STATUS_URL).respond(
        json=load_json("utilities_status_response_200"),
        status_code=200,
        headers={"cf-ray": "status-1"},
    )
    client.__dict__.pop("_extract_rate_limits", None)

    statuses = client.utilities.status(output_format=OutputFormat.INTERNAL)

    meta = get_meta(statuses)
    assert meta.request_id == "status-1"
    assert meta.status_code == 200
    assert meta.rate_limits is None


def test_every_response_logs_its_credits_at_debug(respx_mock, real_headers):
    respx_mock.get(PRICES_URL).respond(
        json=prices_body(), status_code=200, headers=credit_headers(3, 97)
    )
    with patch.object(real_headers.logger, "debug") as debug:
        real_headers.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    lines = [str(call.args[0]) for call in debug.call_args_list]
    assert any(
        line.startswith("Credits: 3 consumed, 97/100 remaining") for line in lines
    )


def test_the_client_has_no_public_rate_limits_snapshot(client):
    assert not hasattr(client, "rate_limits")


def test_meta_is_exported_from_the_package_root():
    assert marketdata.get_meta is get_meta
    assert marketdata.ResponseMeta is ResponseMeta
    assert marketdata.UserRateLimits is UserRateLimits
    for name in ("ResponseMeta", "get_meta", "UserRateLimits"):
        assert name in marketdata.__all__


# ---------------------------------------------------------------- unit


def limits(consumed, remaining, reset=RESET, limit=100):
    return UserRateLimits(
        credit_limit=limit,
        credits_remaining=remaining,
        reset_time=reset,
        credits_consumed=consumed,
    )


def test_attach_and_get_meta_on_plain_values():
    meta = ResponseMeta(status_code=200, request_id=None, rate_limits=None)

    assert attach_meta(None, meta) is None
    assert get_meta(None) is None
    assert get_meta("plain") is None
    assert get_meta(object()) is None
    wrapped = attach_meta([1, 2], meta)
    assert wrapped == [1, 2] and get_meta(wrapped) is meta
    assert get_meta(attach_meta({"a": 1}, meta)) is meta
    assert get_meta(attach_meta("out.csv", meta)) is meta
    # Not weak-referenceable: returned untouched, nothing to read back.
    plain = object()
    assert attach_meta(plain, meta) is plain
    assert get_meta(plain) is None


def test_models_are_remembered_by_identity_and_forgotten_with_the_object():
    @dataclass
    class Model:
        x: int

    meta = ResponseMeta(status_code=200, request_id=None, rate_limits=None)
    model = attach_meta(Model(1), meta)
    key = id(model)

    assert get_meta(model) is meta
    assert vars(model) == {"x": 1}
    assert key in _registry

    del model
    gc.collect()
    assert key not in _registry


def test_merge_sums_credits_and_keeps_the_newest_window():
    first = ResponseMeta(200, "r1", limits(2, 98, reset=RESET))
    late = ResponseMeta(200, "r2", limits(3, 40, reset=RESET - 3600))  # old window
    last = ResponseMeta(203, "r3", limits(4, 90, reset=RESET + 3600, limit=200))

    merged = ResponseMeta.merge([first, late, last])

    assert merged.responses == 3
    assert merged.status_code == 203 and merged.request_id == "r3"
    # Every response was billed, whichever window billed it.
    assert merged.rate_limits.credits_consumed == 9
    # The balance belongs to the newest window: 40 and 98 are counts of
    # windows that have already closed.
    assert merged.rate_limits.credits_remaining == 90
    assert merged.rate_limits.credit_limit == 200
    assert merged.rate_limits.reset_time == last.rate_limits.reset_time


def test_merge_takes_the_lowest_balance_inside_the_newest_window():
    """Two responses of the same window: the lowest count is the balance after
    the call, whatever order they completed in."""
    first = ResponseMeta(200, "r1", limits(2, 98, reset=RESET))
    second = ResponseMeta(200, "r2", limits(3, 95, reset=RESET))

    merged = ResponseMeta.merge([second, first])

    assert merged.rate_limits.credits_remaining == 95
    assert merged.rate_limits.credits_consumed == 5


def test_merge_does_not_carry_a_closed_window_balance_across_a_reset():
    """A call whose retry crosses the reset: the credits went back up, so the
    pre-reset count paired with the new window's `reset_time` would report a
    state that never existed (the rule `RateLimitTracker` already applies)."""
    before = ResponseMeta(503, "r1", limits(0, 2, reset=RESET))
    after = ResponseMeta(200, "r2", limits(1, 99, reset=RESET + 60))

    merged = ResponseMeta.merge([before, after])

    assert merged.rate_limits.credits_remaining == 99
    assert merged.rate_limits.reset_time == after.rate_limits.reset_time
    assert merged.rate_limits.credits_consumed == 1


def test_merge_without_credit_headers_has_no_rate_limits():
    metas = [ResponseMeta(200, "a", None), ResponseMeta(200, "b", None)]

    merged = ResponseMeta.merge(metas)

    assert merged.rate_limits is None
    assert merged.responses == 2
    assert merged.request_id == "b"
