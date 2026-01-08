from marketdata.api_status import API_STATUS_DATA, APIStatusResult


def test_api_status_data(load_json, respx_mock, client):
    mock_data = load_json("api_status_response_200")

    respx_mock.get("https://api.marketdata.app/status/").respond(
        json=mock_data,
        status_code=200,
    )

    API_STATUS_DATA.refresh(client)
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/chain/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/expirations/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/lookup/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/quotes/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/strikes/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/bulkcandles/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/bulkquotes/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/candles/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/earnings/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/news/")
        == APIStatusResult.ONLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/quotes/")
        == APIStatusResult.ONLINE
    )


def test_api_status_data_offline(load_json, respx_mock, client):
    mock_data = load_json("api_status_response_200")

    mock_data["status"] = [
        "offline",
        "offline",
        "offline",
        "offline",
        "offline",
        "offline",
        "offline",
        "offline",
        "offline",
        "offline",
        "offline",
        "offline",
    ]
    mock_data["online"] = [
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json=mock_data,
        status_code=200,
    )

    API_STATUS_DATA.refresh(client)
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/chain/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/expirations/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/lookup/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/quotes/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/options/strikes/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/bulkcandles/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/bulkquotes/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/candles/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/earnings/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/news/")
        == APIStatusResult.OFFLINE
    )
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/stocks/quotes/")
        == APIStatusResult.OFFLINE
    )


def test_api_status_data_unknown(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(
        status_code=500,
    )

    API_STATUS_DATA.refresh(client)
    assert (
        API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
        == APIStatusResult.UNKNOWN
    )


def test_api_status_data_service_not_online(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json={
            "s": "ok",
            "service": ["/v1/markets/status/"],
            "status": ["online"],
            "online": [False],
            "uptimePct30d": [0],
            "uptimePct90d": [0],
            "updated": [0],
        },
        status_code=200,
    )
    status = API_STATUS_DATA.get_api_status(client, "/v1/markets/status/")
    assert status == APIStatusResult.OFFLINE


def test_api_status_data_service_not_found(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/status/").respond(
        json={
            "s": "ok",
            "service": ["/v1/markets/status/"],
            "status": ["online"],
            "online": [True],
        },
        status_code=200,
    )

    API_STATUS_DATA.refresh(client)
    assert (
        API_STATUS_DATA.get_api_status(client, "invalid_service")
        == APIStatusResult.UNKNOWN
    )
