"""Live tests for the utilities resource: status, headers, user."""

import datetime
import ipaddress

from marketdata import MarketDataClient, OutputFormat
from marketdata.output_types.utilities_headers import RequestHeaders
from marketdata.output_types.utilities_status import ServiceStatus
from marketdata.output_types.utilities_user import User


def test_status_lists_every_service(live_client: MarketDataClient):
    statuses = live_client.utilities.status(output_format=OutputFormat.INTERNAL)

    assert isinstance(statuses, list), statuses
    assert len(statuses) >= 1
    for entry in statuses:
        assert isinstance(entry, ServiceStatus)
        assert entry.service.startswith("/v1/")
        assert entry.status in {"online", "offline"}
        assert isinstance(entry.online, bool)
        assert 0 <= entry.uptimePct30d <= 1
        assert 0 <= entry.uptimePct90d <= 1
        assert isinstance(entry.updated, datetime.datetime)
    assert "/v1/stocks/quotes/" in {entry.service for entry in statuses}


def test_headers_echo_the_sdk_request(live_client: MarketDataClient):
    headers = live_client.utilities.headers(output_format=OutputFormat.INTERNAL)

    assert isinstance(headers, RequestHeaders), headers
    assert headers.user_agent == live_client.library_user_agent
    # The API echoes the header but masks the token itself.
    assert headers.authorization.startswith("Bearer ")
    assert live_client.token not in headers.authorization
    assert headers.get("cf-ray")
    ipaddress.ip_address(headers.detected_ip)


def test_user_returns_plan_counters(live_client: MarketDataClient):
    user = live_client.utilities.user(output_format=OutputFormat.INTERNAL)

    assert isinstance(user, User), user
    assert user.credit_limit > 0
    # The balance can go negative after an oversized request, so only the
    # upper bound is a contract.
    assert user.credits_remaining <= user.credit_limit
    assert isinstance(user.options_data_permissions, str)
    # The call also refreshes the client's rate-limit snapshot.
    assert live_client.rate_limits.requests_limit == user.credit_limit
