"""Issue #44: the API's IP headers. `X-API-Authorized-IP` on a 403 block names
the address the account is bound to, and `X-API-Detected-IP` on any answer
names the address the call came from. The legacy `X-API-BLOCKED-IP`, which
carries whichever of the two applies, is deliberately not read: the API is
removing it (MarketData-App/api#202)."""

import httpx
import pytest

from marketdata.exceptions import ForbiddenError
from marketdata.input_types.base import OutputFormat
from marketdata.meta import ResponseMeta, get_meta

PRICES_URL = "https://api.marketdata.app/v1/stocks/prices/"
CALL_URL = "https://api.marketdata.app/v1/options/quotes/AAPL250117C00150000/"
PUT_URL = "https://api.marketdata.app/v1/options/quotes/AAPL250117P00150000/"
SYMBOLS = ["AAPL250117C00150000", "AAPL250117P00150000"]
BLOCKED = {"s": "error", "errmsg": "Access denied."}
AUTHORIZED_IP = "203.0.113.7"
DETECTED_IP = "198.51.100.24"
OTHER_IP = "198.51.100.99"
PRICES_BODY = {"s": "ok", "symbol": ["AAPL"], "mid": [1.0]}


def _quote(load_json, detected_ip=None, status_code=200):
    headers = {"x-api-detected-ip": detected_ip} if detected_ip else {}
    return httpx.Response(
        status_code, json=load_json("options_quotes_response_200"), headers=headers
    )


# ------------------------------------------------------------ the 403 block


def test_an_ip_block_names_the_address_the_account_is_authorized_for(
    respx_mock, client
):
    respx_mock.get(PRICES_URL).respond(
        json=BLOCKED, status_code=403, headers={"X-API-Authorized-IP": AUTHORIZED_IP}
    )

    with pytest.raises(ForbiddenError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.authorized_ip == AUTHORIZED_IP
    # In the message too: a caller who prints the exception and nothing else
    # would otherwise read "Access denied." with no way to know what to allow.
    assert AUTHORIZED_IP in error.message
    assert "Access denied." in error.message


def test_a_403_that_is_not_an_ip_block_carries_no_address(respx_mock, client):
    respx_mock.get(PRICES_URL).respond(json=BLOCKED, status_code=403)

    with pytest.raises(ForbiddenError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    error = exc_info.value
    assert error.authorized_ip is None
    assert error.message == BLOCKED["errmsg"]


def test_the_legacy_blocked_ip_header_is_not_read(respx_mock, client):
    """`X-API-BLOCKED-IP` is the header the API is removing. Reading it would
    put this SDK back in the way of that removal, which is what #44 exists to
    clear."""
    respx_mock.get(PRICES_URL).respond(
        json=BLOCKED, status_code=403, headers={"X-API-BLOCKED-IP": AUTHORIZED_IP}
    )

    with pytest.raises(ForbiddenError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert exc_info.value.authorized_ip is None


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (f"  {AUTHORIZED_IP} ", AUTHORIZED_IP),
        ("", None),
        ("   ", None),
    ],
    ids=["padded", "empty", "blank"],
)
def test_the_address_is_read_as_the_value_it_names(
    respx_mock, client, header, expected
):
    """A header that is padded or empty must not reach the caller verbatim:
    `exc.authorized_ip == my_own_ip` is the comparison this exists for."""
    respx_mock.get(PRICES_URL).respond(
        json=BLOCKED, status_code=403, headers={"X-API-Authorized-IP": header}
    )

    with pytest.raises(ForbiddenError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert exc_info.value.authorized_ip == expected


def test_the_sentence_reads_on_its_own_when_the_api_sent_no_message(respx_mock, client):
    """A 403 whose body carries no `errmsg` leaves the message empty, and the
    sentence must not arrive with a space in front of it."""
    respx_mock.get(PRICES_URL).respond(
        text="", status_code=403, headers={"X-API-Authorized-IP": AUTHORIZED_IP}
    )

    with pytest.raises(ForbiddenError) as exc_info:
        client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert exc_info.value.message == f"This account is authorized for {AUTHORIZED_IP}."


def test_an_ip_block_on_one_symbol_of_a_fan_out_still_names_the_address(
    load_json, respx_mock, client
):
    respx_mock.get(CALL_URL).mock(return_value=_quote(load_json, DETECTED_IP))
    respx_mock.get(PUT_URL).respond(
        json=BLOCKED, status_code=403, headers={"X-API-Authorized-IP": AUTHORIZED_IP}
    )

    with pytest.raises(ForbiddenError) as exc_info:
        client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    assert exc_info.value.authorized_ip == AUTHORIZED_IP


# ------------------------------------------------------ the detected address


@pytest.mark.parametrize("status_code", [200, 203])
def test_an_answer_reports_the_address_it_came_from(respx_mock, client, status_code):
    respx_mock.get(PRICES_URL).respond(
        json=PRICES_BODY,
        status_code=status_code,
        headers={"X-API-Detected-IP": f" {DETECTED_IP} "},
    )

    prices = client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert get_meta(prices).detected_ip == DETECTED_IP


def test_an_answer_without_the_header_reports_no_address(respx_mock, client):
    """The API resolves the address for an account bound to one, which is the
    ordinary case; an account allowed to call from several, a staff token and
    the Sheets add-on get no header, and its absence must not read as an
    address."""
    respx_mock.get(PRICES_URL).respond(json=PRICES_BODY, status_code=200)

    prices = client.stocks.prices("AAPL", output_format=OutputFormat.JSON)

    assert get_meta(prices).detected_ip is None


def test_the_empty_answer_reports_the_address_too(respx_mock, client):
    """The API sends the header on the answers it serves, the 404 `no_data`
    included, and that answer is a result rather than an error here."""
    respx_mock.get(PRICES_URL).respond(
        json={"s": "no_data"},
        status_code=404,
        headers={"X-API-Detected-IP": DETECTED_IP},
    )

    prices = client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)

    assert prices == []
    assert get_meta(prices).detected_ip == DETECTED_IP


def test_the_merged_address_comes_from_the_response_that_speaks_for_the_call():
    """Two addresses can only disagree if something between the client and the
    API rewrote one (a dual-stack host, an egress pool). The value comes from
    the same response as `status_code` and `request_id`, so the three describe
    one exchange; taking whichever response reported one last would make it
    depend on which worker thread finished first, which is not something a
    caller can reason about. Asserted on `merge` itself: through a fan-out the
    order of the recorded responses is the order they arrived in."""
    metas = [
        ResponseMeta(200, "r1", None, detected_ip=OTHER_IP),
        ResponseMeta(200, "r2", None, detected_ip=DETECTED_IP),
    ]

    merged = ResponseMeta.merge(metas)

    assert merged.request_id == "r2"
    assert merged.detected_ip == DETECTED_IP


def test_a_fan_out_reports_the_address_its_responses_agree_on(
    load_json, respx_mock, client
):
    respx_mock.get(CALL_URL).mock(return_value=_quote(load_json, DETECTED_IP))
    respx_mock.get(PUT_URL).mock(return_value=_quote(load_json, DETECTED_IP))

    quotes = client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    meta = get_meta(quotes)
    assert meta.responses == 2
    assert meta.detected_ip == DETECTED_IP


def test_the_merge_falls_back_to_any_response_that_reported_an_address(
    load_json, respx_mock, client
):
    """A speaker without the header says nothing rather than "no address":
    every request of a call leaves from the same machine."""
    respx_mock.get(CALL_URL).mock(return_value=_quote(load_json, DETECTED_IP))
    respx_mock.get(PUT_URL).mock(return_value=_quote(load_json))

    quotes = client.options.quotes(SYMBOLS, output_format=OutputFormat.JSON)

    assert get_meta(quotes).detected_ip == DETECTED_IP


def test_merging_nothing_but_headerless_responses_reports_no_address():
    metas = [
        ResponseMeta(status_code=200, request_id="r1", rate_limits=None),
        ResponseMeta(status_code=200, request_id="r2", rate_limits=None),
    ]

    assert ResponseMeta.merge(metas).detected_ip is None


def test_the_speaker_is_the_last_usable_response_not_the_last_one():
    """`merge` skips a response that could not have contributed to the result,
    and the address follows the same rule."""
    metas = [
        ResponseMeta(200, "r1", None, detected_ip=DETECTED_IP),
        ResponseMeta(404, "r2", None, detected_ip=OTHER_IP),
    ]

    assert ResponseMeta.merge(metas).detected_ip == DETECTED_IP
