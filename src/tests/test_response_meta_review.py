"""The review findings on #81: what may reach the pre-flight state, which
response the metadata of a failed call speaks for, and an exception's ability
to carry that metadata at all."""

import time

import httpx
import pytest

import marketdata
from marketdata.exceptions import (
    BadRequestError,
    NetworkError,
    ParseError,
    RateLimitError,
    ServerError,
)
from marketdata.input_types.base import OutputFormat
from marketdata.meta import ResponseMeta, attach_meta, get_meta
from marketdata.rate_limit_tracker import RateLimitTracker
from marketdata.types import UserRateLimits


def use_real_header_extraction(client):
    """The conftest client patches header extraction at the instance level, so
    every answer feeds the tracker the fixture's own numbers. These tests read
    the credit headers their mocked answers really carry."""
    client.__dict__.pop("_extract_rate_limits", None)
    return client


PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"
CALL_URL = "https://api.marketdata.app/v1/options/quotes/AAPL250117C00150000/"
PUT_URL = "https://api.marketdata.app/v1/options/quotes/AAPL250117P00150000/"
SYMBOLS = ["AAPL250117C00150000", "AAPL250117P00150000"]
RESET = 1789050420
LATER_WINDOW = RESET + 3600


def credit_headers(limit, remaining, reset=RESET, consumed=1):
    return {
        "x-api-ratelimit-limit": str(limit),
        "x-api-ratelimit-remaining": str(remaining),
        "x-api-ratelimit-reset": str(reset),
        "x-api-ratelimit-consumed": str(consumed),
    }


def account_state(remaining=59, reset=RESET):
    return UserRateLimits(
        credit_limit=100,
        credits_remaining=remaining,
        reset_time=reset,
        credits_consumed=100 - remaining,
    )


# ------------------------------------------- what may reach the pre-flight


@pytest.mark.parametrize("status_code", [203, 401, 429])
def test_a_zero_limit_envelope_never_becomes_the_accounts_state(
    respx_mock, client, status_code
):
    """The API answers a missing, malformed or unknown token with demo data
    and a `0/0` credit envelope belonging to another window (verified live: a
    bad token gets a 203 with `limit: 0`). Recording it would tell the
    pre-flight check this account has no credits, and the ordering rule would
    then keep the real state out until that other window passed."""
    use_real_header_extraction(client)
    state = account_state()
    client._rate_limits.reset(state)
    respx_mock.get(PRICES_URL).respond(
        json={"s": "ok", "symbol": ["AAPL"], "mid": [1.0]},
        status_code=status_code,
        headers=credit_headers(0, 0, reset=LATER_WINDOW),
    )

    try:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
    except marketdata.BaseMarketdataException:
        pass

    assert client._rate_limits.state is state


def test_an_error_answer_of_this_account_still_updates_the_state(respx_mock, client):
    """The guard is about whose envelope it is, not about the status: a 429
    reports this account's exhausted balance, and that is exactly what the
    pre-flight check is for."""
    use_real_header_extraction(client)
    client._rate_limits.reset(account_state())
    respx_mock.get(PRICES_URL).respond(
        json={"s": "error", "errmsg": "Rate limit exceeded"},
        status_code=429,
        headers=credit_headers(100, 0),
    )

    with pytest.raises(marketdata.RateLimitError):
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert client._rate_limits.state.credits_remaining == 0


def test_the_user_endpoint_replaces_a_state_the_ordering_rule_would_keep(
    respx_mock, client
):
    """`update` ignores a higher balance in the same window, since that is what
    a late answer looks like. An answer asked for precisely to learn the
    balance is not late, so it replaces the state; otherwise a caller has no
    way to correct one."""
    use_real_header_extraction(client)
    client._rate_limits.reset(account_state(remaining=0))
    respx_mock.get("https://api.marketdata.app/user/").respond(
        json={"s": "ok", "id": [1], "plan": ["Trader"]},
        status_code=200,
        headers=credit_headers(100, 90),
    )

    client.utilities.user(output_format=OutputFormat.JSON)

    assert client._rate_limits.state.credits_remaining == 90


def test_the_tracker_ignores_an_envelope_with_no_credits_at_all():
    tracker = RateLimitTracker()
    tracker.update(UserRateLimits(0, 0, RESET, 0))

    assert tracker.state is None


def test_an_authoritative_update_skips_the_ordering_rule():
    tracker = RateLimitTracker()
    tracker.reset(account_state(remaining=0))

    tracker.update(account_state(remaining=90), authoritative=True)

    assert tracker.state.credits_remaining == 90


# ------------------------------------ which response a failure speaks for


def test_a_partial_fan_out_failure_reports_the_request_that_failed(
    load_json, respx_mock, client
):
    """The metadata of a failure names the request that failed, as the
    exception does: that is the request a support ticket is about, not the
    sibling that came back fine."""
    respx_mock.get(CALL_URL).respond(
        json=load_json("options_quotes_response_200"),
        status_code=200,
        headers={"cf-ray": "ok-1"},
    )
    respx_mock.get(PUT_URL).respond(
        json={"s": "error", "errmsg": "Bad parameters"},
        status_code=400,
        headers={"cf-ray": "bad-1"},
    )

    with pytest.raises(BadRequestError) as exc_info:
        client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    meta = get_meta(exc_info.value)
    assert meta.responses == 2
    assert (meta.status_code, meta.request_id) == (400, "bad-1")
    assert (exc_info.value.status_code, exc_info.value.request_id) == (400, "bad-1")


def test_a_retried_chunk_that_never_recovers_reports_its_own_status(
    load_json, respx_mock, client, monkeypatch
):
    monkeypatch.setattr(
        marketdata.api_status.API_STATUS_DATA,
        "_trigger_async_refresh",
        lambda c: None,
    )
    respx_mock.get(CALL_URL).respond(
        json=load_json("options_quotes_response_200"),
        status_code=200,
        headers={"cf-ray": "ok-1"},
    )
    respx_mock.get(PUT_URL).respond(
        json={}, status_code=503, headers={"cf-ray": "down-1"}
    )

    with pytest.raises(ServerError) as exc_info:
        client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    meta = get_meta(exc_info.value)
    assert meta.status_code == 503
    assert meta.request_id == "down-1"


def test_a_successful_call_still_speaks_for_a_usable_response(
    load_json, respx_mock, client
):
    """The other half of the rule, unchanged: a symbol that answered `no_data`
    is recorded and then dropped from the merge, and must not label the
    result."""
    respx_mock.get(CALL_URL).respond(
        json=load_json("options_quotes_response_200"),
        status_code=200,
        headers={"cf-ray": "ok-1"},
    )
    respx_mock.get(PUT_URL).respond(
        json={"s": "no_data"}, status_code=404, headers={"cf-ray": "empty-1"}
    )

    quotes = client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    meta = get_meta(quotes)
    assert (meta.status_code, meta.request_id) == (200, "ok-1")


# The review of #88 (#104): the responses are recorded in the order the
# requests finished, so no rule over that list can tell which one failed. The
# exception can: the metadata of a failure describes the request it is about.


def later(response: httpx.Response, delay: float = 0.2):
    """Answer after the other requests of the call, so this response is
    recorded last: the order in which a rule over the list went wrong."""

    def answer(request: httpx.Request) -> httpx.Response:
        time.sleep(delay)
        return response

    return answer


def _speaker(meta: ResponseMeta) -> tuple[int, str | None]:
    return meta.status_code, meta.request_id


def test_a_failure_names_the_request_that_failed_not_a_later_empty_symbol(
    respx_mock, client
):
    respx_mock.get(CALL_URL).respond(
        json={"s": "error", "errmsg": "Bad parameters"},
        status_code=400,
        headers={"cf-ray": "bad-1"},
    )
    respx_mock.get(PUT_URL).mock(
        side_effect=later(
            httpx.Response(404, json={"s": "no_data"}, headers={"cf-ray": "empty-1"})
        )
    )

    with pytest.raises(BadRequestError) as exc_info:
        client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    meta = get_meta(exc_info.value)
    assert meta.responses == 2
    assert _speaker(meta) == (400, "bad-1")


def test_a_failure_names_the_request_that_failed_not_a_later_server_error(
    respx_mock, client
):
    client.max_retries = 0
    respx_mock.get(CALL_URL).respond(
        json={"s": "error", "errmsg": "Bad parameters"},
        status_code=400,
        headers={"cf-ray": "bad-1"},
    )
    respx_mock.get(PUT_URL).mock(
        side_effect=later(httpx.Response(503, json={}, headers={"cf-ray": "down-1"}))
    )

    with pytest.raises(BadRequestError) as exc_info:
        client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    assert _speaker(get_meta(exc_info.value)) == (400, "bad-1")


def test_an_undecodable_chunk_is_named_even_though_every_status_was_usable(
    respx_mock, client
):
    """Every answer is a 200, so no status says which one broke the call; only
    the `ParseError` does."""
    starts = iter(["html", "ok"])

    def answer(request: httpx.Request) -> httpx.Response:
        if next(starts) == "html":
            return httpx.Response(200, text="<html>", headers={"cf-ray": "html-1"})
        time.sleep(0.2)
        return httpx.Response(
            200, json={"s": "ok", "t": [1], "c": [1.0]}, headers={"cf-ray": "ok-1"}
        )

    respx_mock.get(url__regex=r".*/stocks/candles/H/AAPL/.*").mock(side_effect=answer)

    with pytest.raises(ParseError) as exc_info:
        client.stocks.candles(
            "AAPL",
            resolution="H",
            from_date="2023-01-01",
            to_date="2024-06-01",
            output_format=OutputFormat.JSON,
        )

    assert exc_info.value.request_id == "html-1"
    assert _speaker(get_meta(exc_info.value)) == (200, "html-1")


def test_a_request_that_got_no_answer_lends_the_failure_no_sibling_id(
    respx_mock, client
):
    """A transport failure has no response, so its metadata has no status and
    no id to report, as the exception itself says (`0` and `N/A`); the credits
    of the sibling that did answer are still reported."""
    client.max_retries = 0
    respx_mock.get(CALL_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    respx_mock.get(PUT_URL).mock(
        side_effect=later(
            httpx.Response(200, json={"s": "ok"}, headers={"cf-ray": "ok-1"})
        )
    )

    with pytest.raises(NetworkError) as exc_info:
        client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    meta = get_meta(exc_info.value)
    assert (exc_info.value.status_code, exc_info.value.request_id) == (0, "N/A")
    assert _speaker(meta) == (0, None)
    assert meta.responses == 1
    assert meta.rate_limits.credits_consumed == 1


REQUEST = httpx.Request("GET", CALL_URL)


def _response(status: int, ray: str) -> httpx.Response:
    return httpx.Response(status, json={}, headers={"cf-ray": ray}, request=REQUEST)


@pytest.mark.parametrize("reverse", [False, True])
def test_the_exceptions_response_speaks_whatever_the_order(reverse):
    metas = [
        ResponseMeta(400, "bad-1", None),
        ResponseMeta(404, "empty-1", None),
        ResponseMeta(503, "down-1", None),
        ResponseMeta(200, "ok-1", None),
    ]
    if reverse:
        metas.reverse()
    error = BadRequestError("bad", request=REQUEST, response=_response(400, "bad-1"))

    merged = ResponseMeta.merge(metas, error=error)

    assert _speaker(merged) == (400, "bad-1")
    assert merged.responses == 4


@pytest.mark.parametrize(
    "error",
    [
        NetworkError("timed out", request=REQUEST),
        RateLimitError("Rate limit exceeded"),
    ],
    ids=["transport-failure", "pre-flight"],
)
def test_a_failure_without_a_response_has_no_speaker(error):
    limits = UserRateLimits(100, 90, RESET, 3)
    metas = [ResponseMeta(200, "ok-1", limits), ResponseMeta(503, "down-1", None)]

    merged = ResponseMeta.merge(metas, error=error)

    assert _speaker(merged) == (0, None)
    assert merged.rate_limits.credits_consumed == 3


def test_a_response_without_a_cf_ray_gives_no_request_id():
    """The exception reads a missing `cf-ray` as the sentinel `"N/A"`; the
    metadata reads it as `None`, as on a successful call."""
    error = BadRequestError(
        "bad", request=REQUEST, response=httpx.Response(400, request=REQUEST)
    )

    merged = ResponseMeta.merge([ResponseMeta(400, None, None)], error=error)

    assert error.request_id == "N/A"
    assert _speaker(merged) == (400, None)


def test_a_response_that_is_not_an_httpx_response_does_not_break_the_merge():
    """The merge runs inside the decorator's `except`: were it to raise there,
    the caller would get that error instead of their own. A `response` of
    another type (a caller's subclass, a test double) falls back to the rule
    of a successful call."""
    error = BadRequestError("bad", request=REQUEST, response=_response(400, "bad-1"))
    error.response = object()
    metas = [ResponseMeta(200, "ok-1", None), ResponseMeta(404, "empty-1", None)]

    assert _speaker(ResponseMeta.merge(metas, error=error)) == (200, "ok-1")


def test_the_no_usable_answer_error_names_the_answer_that_is_not_empty(
    respx_mock, client
):
    """`options.quotes` raises its own `MarketdataHttpError` when no symbol
    answered with anything usable. It used to hand over the first response,
    which can be a symbol that simply had no data, and the metadata now reads
    the exception's response."""
    respx_mock.get(CALL_URL).respond(
        json={"s": "no_data"}, status_code=404, headers={"cf-ray": "empty-1"}
    )
    respx_mock.get(PUT_URL).mock(
        side_effect=later(httpx.Response(204, headers={"cf-ray": "odd-1"}))
    )

    with pytest.raises(marketdata.MarketdataHttpError) as exc_info:
        client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    assert exc_info.value.message == "No responses from API"
    assert (exc_info.value.status_code, exc_info.value.request_id) == (204, "odd-1")
    assert _speaker(get_meta(exc_info.value)) == (204, "odd-1")


def test_an_exception_not_about_a_request_keeps_the_rule_of_a_success():
    """A CSV path that already exists: every request answered, so neither an
    empty symbol nor an attempt that failed and recovered is what went wrong,
    and the metadata speaks for the last usable response."""
    metas = [
        ResponseMeta(200, "ok-1", None),
        ResponseMeta(503, "down-1", None),
        ResponseMeta(200, "ok-2", None),
        ResponseMeta(404, "empty-1", None),
    ]

    merged = ResponseMeta.merge(metas, error=FileExistsError("mine.csv"))

    assert _speaker(merged) == (200, "ok-2")


# --------------------------------- an exception that can carry the metadata


def test_a_builtin_exception_carries_the_metadata_of_the_call_it_failed(
    respx_mock, client, tmp_path
):
    """`get_meta(exc) is None` means the call never reached the API. A call
    billed 10 credits that then fails writing its file must not say that, and
    a built-in exception cannot be weak-referenced, so the identity registry
    could not hold its metadata."""
    use_real_header_extraction(client)
    target = tmp_path / "mine.csv"

    def _create_target_meanwhile(request: httpx.Request) -> httpx.Response:
        # The #43 race: the path appears between the check and the write, so
        # the exclusive create fails after the API has already billed the call.
        target.write_text("someone else's data", encoding="utf-8")
        return httpx.Response(
            200,
            text="symbol,mid\r\nAAPL,1.0\r\n",
            headers=credit_headers(100, 90, consumed=10),
        )

    respx_mock.get(PRICES_URL).mock(side_effect=_create_target_meanwhile)

    with pytest.raises(FileExistsError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.CSV, filename=target)

    meta = get_meta(exc_info.value)
    assert meta is not None
    assert meta.rate_limits.credits_consumed == 10
    assert target.read_text(encoding="utf-8") == "someone else's data"


def test_attaching_to_an_exception_keeps_the_exception_itself():
    error = ValueError("boom")
    meta = ResponseMeta(200, "r1", None)

    assert attach_meta(error, meta) is error
    assert get_meta(error) is meta
    assert str(error) == "boom"


def test_a_result_that_cannot_be_weak_referenced_says_so(caplog):
    """Nothing in the SDK returns one today, since exceptions take the
    attribute path, but dropping metadata in silence is how a caller ends up
    believing a call never reached the API."""
    meta = ResponseMeta(200, "r1", None)

    with caplog.at_level("DEBUG", logger="marketdata.logger"):
        assert attach_meta(42, meta) == 42

    assert get_meta(42) is None
    assert "cannot be weak-referenced" in caplog.text
