"""Caller-supplied input must not be able to smuggle path segments, query
params or fragments into outbound request URLs (see SECURITY.md)."""

from marketdata.input_types.base import OutputFormat


def test_symbol_path_traversal_is_encoded(load_json, respx_mock, client):
    mock_data = load_json("stocks_earnings_response_200")
    route = respx_mock.get(url__regex=r".*earnings.*").respond(
        json=mock_data, status_code=200
    )

    client.stocks.earnings(symbol="AAPL/../../user", output_format=OutputFormat.JSON)

    raw_path = route.calls.last.request.url.raw_path.decode()
    assert raw_path.startswith("/v1/stocks/earnings/AAPL%2F..%2F..%2Fuser/")
    assert "/../" not in raw_path


def test_symbol_query_smuggling_is_encoded(load_json, respx_mock, client):
    mock_data = load_json("stocks_earnings_response_200")
    route = respx_mock.get(url__regex=r".*earnings.*").respond(
        json=mock_data, status_code=200
    )

    client.stocks.earnings(symbol="AAPL?injected=1", output_format=OutputFormat.JSON)

    raw_path = route.calls.last.request.url.raw_path.decode()
    assert raw_path.startswith("/v1/stocks/earnings/AAPL%3Finjected%3D1/")
    assert "injected=1" not in str(route.calls.last.request.url.params)


def test_valid_symbol_is_unchanged(load_json, respx_mock, client):
    mock_data = load_json("stocks_earnings_response_200")
    route = respx_mock.get(
        "https://api.marketdata.app/v1/stocks/earnings/BRK.B/"
    ).respond(json=mock_data, status_code=200)

    client.stocks.earnings(symbol="BRK.B", output_format=OutputFormat.JSON)

    assert route.called


def test_lookup_dot_segments_are_encoded(load_json, respx_mock, client):
    mock_data = load_json("options_lookup_response_200")
    route = respx_mock.get(url__regex=r".*lookup.*").respond(
        json=mock_data, status_code=200
    )

    client.options.lookup(lookup="AAPL/../../user", output_format=OutputFormat.JSON)

    raw_path = route.calls.last.request.url.raw_path.decode()
    assert "/../" not in raw_path
    assert "/%2E%2E/" in raw_path


def test_lookup_valid_string_keeps_slashes(load_json, respx_mock, client):
    mock_data = load_json("options_lookup_response_200")
    route = respx_mock.get(url__regex=r".*lookup.*").respond(
        json=mock_data, status_code=200
    )

    client.options.lookup(
        lookup="AAPL 7/28/2023 200 Call", output_format=OutputFormat.JSON
    )

    raw_path = route.calls.last.request.url.raw_path.decode()
    assert raw_path.startswith("/v1/options/lookup/AAPL%207/28/2023%20200%20Call/")
