import datetime
import pathlib
from unittest.mock import patch

import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.output_types.options_chain import (
    OptionsChain,
    OptionsChainHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult


def test_options_chain_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )

    instance = OptionsChain(
        s="ok",
        optionSymbol=["AAPL"],
        underlying=["AAPL"],
        expiration=[timestamp],
        side=["call"],
        strike=["150"],
        firstTraded=[timestamp],
        dte=["1"],
        updated=[timestamp],
        bid=["150"],
        bidSize=["100"],
        mid=["150"],
        ask=["150"],
        askSize=["100"],
        last=["150"],
        openInterest=["100"],
        volume=["100"],
        inTheMoney=["True"],
        intrinsicValue=["150"],
        extrinsicValue=["150"],
        underlyingPrice=["150"],
        iv=["150"],
        delta=["150"],
        gamma=["150"],
        theta=["150"],
        vega=["150"],
    )

    assert isinstance(str(instance), str)


def test_options_chain_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = OptionsChainHumanReadable(
        Symbol=["AAPL"],
        Underlying=["AAPL"],
        Expiration_Date=[timestamp],
        Option_Side=["call"],
        Strike=[110],
        First_Traded=[timestamp],
        Days_To_Expiration=[0],
        Date=[timestamp],
        Bid=[167.8],
        Bid_Size=[164],
        Mid=[168.62],
        Ask=[169.45],
        Ask_Size=[25],
        Last=[170.55],
        Open_Interest=[11],
        Volume=[0],
        In_The_Money=[True],
        Intrinsic_Value=[169.2],
        Extrinsic_Value=[0.58],
        Underlying_Price=[279.2],
        IV=[0],
        Delta=[1],
        Gamma=[0],
        Theta=[-0.011],
        Vega=[0],
    )
    assert isinstance(str(instance), str)


def test_get_options_chain_response_200_dataframe_pandas(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("options_chain_response_200")

        respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )

        chain = client.options.chain("AAPL", output_format=OutputFormat.DATAFRAME)
        assert "s" not in chain.columns
        assert len(chain) == 75

        assert chain.index.name == "optionSymbol"


def test_get_options_chain_response_200_dataframe_polars(load_json, respx_mock, client):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("options_chain_response_200")

        respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
            json=mock_data,
            status_code=200,
        )
        chain = client.options.chain("AAPL", output_format=OutputFormat.DATAFRAME)
        assert "s" not in chain.columns
        assert len(chain) == 75


def test_get_options_chain_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("options_chain_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    chain = client.options.chain("AAPL", output_format=OutputFormat.INTERNAL)
    assert chain.s == "ok"
    assert len(chain.optionSymbol) == 75
    assert chain.optionSymbol[0] == "AAPL251205C00110000"
    assert chain.underlying[0] == "AAPL"
    assert chain.expiration[0] == datetime.datetime.fromtimestamp(1764968400, tz=pytz.timezone('US/Eastern'))
    assert chain.side[0] == "call"
    assert chain.strike[0] == 110
    assert chain.firstTraded[0] == datetime.datetime.fromtimestamp(1761312600, tz=pytz.timezone('US/Eastern'))
    assert chain.dte[0] == 0
    assert chain.updated[0] == datetime.datetime.fromtimestamp(1764957099, tz=pytz.timezone('US/Eastern'))
    assert chain.bid[0] == 167.8
    assert chain.bidSize[0] == 164
    assert chain.mid[0] == 168.62
    assert chain.ask[0] == 169.45
    assert chain.askSize[0] == 25
    assert chain.last[0] == 170.55
    assert chain.openInterest[0] == 11
    assert chain.volume[0] == 0
    assert chain.inTheMoney[0] == True
    assert chain.intrinsicValue[0] == 169.2
    assert chain.extrinsicValue[0] == 0.58
    assert chain.underlyingPrice[0] == 279.2
    assert chain.iv[0] == 0
    assert chain.delta[0] == 1
    assert chain.gamma[0] == 0
    assert chain.theta[0] == -0.011
    assert chain.vega[0] == 0


def test_get_options_chain_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("options_chain_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    chain = client.options.chain("AAPL", output_format=OutputFormat.JSON)
    assert chain == mock_data


def test_get_options_chain_response_200_expiration_all(load_json, respx_mock, client):
    mock_data = load_json("options_chain_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )
    chain = client.options.chain(
        "AAPL", expiration="all", output_format=OutputFormat.JSON
    )
    assert chain == mock_data
    assert respx_mock.calls.last.request.url.params["expiration"] == "all"

    chain = client.options.chain(
        "AAPL", expiration="ALL", output_format=OutputFormat.JSON
    )
    assert chain == mock_data
    assert respx_mock.calls.last.request.url.params["expiration"] == "all"


def test_get_options_chain_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("options_chain_human_response_200")

    respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
        json=mock_data,
        status_code=200,
    )

    chain = client.options.chain(
        "AAPL", output_format=OutputFormat.INTERNAL, use_human_readable=True
    )

    assert len(chain.Symbol) == 200
    assert chain.Symbol[0] == "AAPL251219C00005000"
    assert chain.Underlying[0] == "AAPL"
    assert chain.Expiration_Date[0] == datetime.datetime.fromtimestamp(1766178000, tz=pytz.timezone('US/Eastern'))
    assert chain.Option_Side[0] == "call"
    assert chain.Strike[0] == 5
    assert chain.First_Traded[0] == datetime.datetime.fromtimestamp(1721136600, tz=pytz.timezone('US/Eastern'))
    assert chain.Days_To_Expiration[0] == 7
    assert chain.Date[0] == datetime.datetime.fromtimestamp(1765556009, tz=pytz.timezone('US/Eastern'))
    assert chain.Bid[0] == 272.3
    assert chain.Bid_Size[0] == 299
    assert chain.Mid[0] == 273.02
    assert chain.Ask[0] == 273.75
    assert chain.Ask_Size[0] == 309
    assert chain.Last[0] == 273.72
    assert chain.Open_Interest[0] == 255
    assert chain.Volume[0] == 20
    assert chain.In_The_Money[0] == True
    assert chain.Intrinsic_Value[0] == 272.7
    assert chain.Extrinsic_Value[0] == 0.32
    assert chain.Underlying_Price[0] == 277.7
    assert chain.IV[0] == 5.0
    assert chain.Delta[0] == 1
    assert chain.Gamma[0] == 0
    assert chain.Theta[0] == -0.0005
    assert chain.Vega[0] == 0


def test_get_options_chain_response_400(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
        json={},
        status_code=400,
    )

    result = client.options.chain(symbol="AAPL", output_format=OutputFormat.INTERNAL)
    assert isinstance(result, MarketDataClientErrorResult)


def test_get_options_chain_status_offline(load_json, respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/options/chain/"],
        "status": ["offline"],
        "online": [False],
        "uptimePct30d": [0],
        "uptimePct90d": [0],
        "updated": [0],
    }

    respx_mock.get("https://api.marketdata.app/status/").respond(
        json=mock_data,
        status_code=200,
    )

    respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
        json={},
        status_code=501,
    )

    chain = client.options.chain("AAPL", output_format=OutputFormat.INTERNAL)
    assert isinstance(chain, MarketDataClientErrorResult)


def test_get_options_chain_response_200_csv(respx_mock, client):
    respx_mock.get("https://api.marketdata.app/v1/options/chain/AAPL/").respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.options.chain(
        "AAPL", output_format=OutputFormat.CSV, filename="test.csv"
    )
    assert pathlib.Path(output).read_text() == "AS RECEIVED FROM API"
