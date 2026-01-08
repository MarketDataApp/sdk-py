import datetime
import pathlib
from unittest.mock import patch

import pytz

from marketdata.input_types.base import OutputFormat
from marketdata.output_types.options_quotes import (
    OptionsQuotes,
    OptionsQuotesHumanReadable,
)
from marketdata.sdk_error import MarketDataClientErrorResult


def test_options_quotes_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )

    instance = OptionsQuotes(
        s="ok",
        optionSymbol=["AAPL271217C00255000"],
        underlying=["AAPL"],
        expiration=[timestamp],
        side=["call"],
        strike=["255"],
        firstTraded=[timestamp],
        dte=["737"],
        updated=[timestamp],
        bid=["65.1"],
        bidSize=["29"],
        mid=["65.75"],
        ask=["66.4"],
        askSize=["84"],
        last=["64.97"],
        openInterest=["588"],
        volume=["0"],
        inTheMoney=["True"],
        intrinsicValue=["23.7344"],
        extrinsicValue=["42.0156"],
        underlyingPrice=["278.7344"],
        iv=["0.2975"],
        delta=["0.7188"],
        gamma=["0.0029"],
        theta=["-0.0403"],
        vega=["1.3368"],
    )
    assert isinstance(str(instance), str)


def test_options_quotes_human_readable_str():
    timestamp = int(
        datetime.datetime(2025, 1, 1, 0, 0, 0, 0, pytz.timezone('US/Eastern')).timestamp()
    )
    instance = OptionsQuotesHumanReadable(
        Symbol=["AAPL271217C00255000"],
        Underlying=["AAPL"],
        Expiration_Date=[timestamp],
        Option_Side=["call"],
        Strike=[250],
        First_Traded=[timestamp],
        Days_To_Expiration=[735],
        Date=[timestamp],
        Bid=[67.05],
        Bid_Size=[337],
        Mid=[68.18],
        Ask=[69.3],
        Ask_Size=[365],
        Last=[67.46],
        Open_Interest=[5094],
        Volume=[10],
        In_The_Money=[True],
        Intrinsic_Value=[28.7943],
        Extrinsic_Value=[39.3857],
        Underlying_Price=[278.7943],
        IV=[0.2974],
        Delta=[0.7336],
        Gamma=[0.0028],
        Theta=[-0.0396],
        Vega=[1.2996],
    )
    assert isinstance(str(instance), str)


def test_get_options_quotes_response_200_internal(load_json, respx_mock, client):
    mock_data = load_json("options_quotes_response_200")

    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        json=mock_data,
        status_code=200,
    )

    quotes = client.options.quotes(
        symbols="AAPL271217C00255000", output_format=OutputFormat.INTERNAL
    )
    assert quotes.s == "ok"
    assert quotes.optionSymbol == ["AAPL271217C00255000"]
    # API returns UTC, convert to US/Eastern for comparison
    expected = datetime.datetime(2025, 12, 10, 19, 49, 56, tzinfo=datetime.timezone.utc).astimezone(pytz.timezone('US/Eastern'))
    assert quotes.updated[0].astimezone(pytz.timezone('US/Eastern')) == expected
    assert quotes.bid[0] == 65.1
    assert quotes.bidSize[0] == 29
    assert quotes.mid[0] == 65.75
    assert quotes.ask[0] == 66.4
    assert quotes.askSize[0] == 84
    assert quotes.last[0] == 64.97
    assert quotes.openInterest[0] == 588
    assert quotes.volume[0] == 0
    assert quotes.inTheMoney[0] == True
    assert quotes.intrinsicValue[0] == 23.7344
    assert quotes.extrinsicValue[0] == 42.0156
    assert quotes.underlyingPrice[0] == 278.7344
    assert quotes.iv[0] == 0.2975
    assert quotes.delta[0] == 0.7188
    assert quotes.gamma[0] == 0.0029
    assert quotes.theta[0] == -0.0403
    assert quotes.vega[0] == 1.3368


def test_get_options_quotes_human_response_200(load_json, respx_mock, client):
    mock_data = load_json("options_quotes_human_response_200")

    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        json=mock_data,
        status_code=200,
    )

    quotes = client.options.quotes(
        symbols="AAPL271217C00255000",
        output_format=OutputFormat.INTERNAL,
        use_human_readable=True,
    )
    assert quotes.Symbol[0] == "AAPL271217C00250000"
    assert quotes.Underlying[0] == "AAPL"
    assert quotes.Expiration_Date[0] == datetime.datetime.fromtimestamp(1829077200, tz=pytz.timezone('US/Eastern'))
    assert quotes.Option_Side[0] == "call"
    assert quotes.Strike[0] == 250
    assert quotes.First_Traded[0] == datetime.datetime.fromtimestamp(1741872600, tz=pytz.timezone('US/Eastern'))
    assert quotes.Days_To_Expiration[0] == 735
    assert quotes.Date[0] == datetime.datetime.fromtimestamp(1765562189, tz=pytz.timezone('US/Eastern'))
    assert quotes.Bid[0] == 67.05
    assert quotes.Bid_Size[0] == 337
    assert quotes.Mid[0] == 68.18
    assert quotes.Ask[0] == 69.3
    assert quotes.Ask_Size[0] == 365
    assert quotes.Last[0] == 67.46
    assert quotes.Open_Interest[0] == 5094
    assert quotes.Volume[0] == 10
    assert quotes.In_The_Money[0] == True
    assert quotes.Intrinsic_Value[0] == 28.7943
    assert quotes.Extrinsic_Value[0] == 39.3857
    assert quotes.Underlying_Price[0] == 278.7943
    assert quotes.IV[0] == 0.2974
    assert quotes.Delta[0] == 0.7336
    assert quotes.Gamma[0] == 0.0028
    assert quotes.Theta[0] == -0.0396
    assert quotes.Vega[0] == 1.2996


def test_get_options_quotes_response_200_json(load_json, respx_mock, client):
    mock_data = load_json("options_quotes_response_200")

    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        json=mock_data,
        status_code=200,
    )

    quotes = client.options.quotes(
        symbols="AAPL271217C00255000", output_format=OutputFormat.JSON
    )
    assert quotes == mock_data


def test_options_quotes_bad_json_response(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        text="",
        status_code=200,
    )

    result = client.options.quotes(
        symbols="AAPL271217C00255000", output_format=OutputFormat.INTERNAL
    )
    assert isinstance(result, OptionsQuotes)
    assert len(result.optionSymbol) == 0


def test_options_quotes_no_one_good_status_code(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        json={
            "s": "error",
        },
        status_code=205,
    )

    result = client.options.quotes(
        symbols="AAPL271217C00255000", output_format=OutputFormat.INTERNAL
    )
    assert isinstance(result, MarketDataClientErrorResult)
    assert result.error.args[0] == "No responses from API"


def test_get_options_quotes_response_200_dataframe_pandas(
    load_json, respx_mock, client
):
    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["pandas"],
    ):
        mock_data = load_json("options_quotes_response_200")

        respx_mock.get(
            "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
        ).respond(
            json=mock_data,
            status_code=200,
        )

        quotes = client.options.quotes(
            symbols="AAPL271217C00255000", output_format=OutputFormat.DATAFRAME
        )
        assert "s" not in quotes.columns
        assert len(quotes) == 1
        assert quotes.index.name == "optionSymbol"
        assert quotes.index.tolist() == ["AAPL271217C00255000"]
        assert quotes.underlying.iloc[0] == "AAPL"
        assert quotes.expiration.iloc[0] == 1829077200
        assert quotes.side.iloc[0] == "call"
        assert quotes.strike.iloc[0] == 255
        assert quotes.firstTraded.iloc[0] == 1741872600
        assert quotes.dte.iloc[0] == 737
        assert quotes.updated.iloc[0] == 1765396196
        assert quotes.bid.iloc[0] == 65.1
        assert quotes.bidSize.iloc[0] == 29
        assert quotes.mid.iloc[0] == 65.75
        assert quotes.ask.iloc[0] == 66.4
        assert quotes.askSize.iloc[0] == 84
        assert quotes.openInterest.iloc[0] == 588
        assert quotes.volume.iloc[0] == 0
        assert quotes.inTheMoney.iloc[0] == True
        assert quotes.intrinsicValue.iloc[0] == 23.7344
        assert quotes.extrinsicValue.iloc[0] == 42.0156
        assert quotes.underlyingPrice.iloc[0] == 278.7344
        assert quotes.delta.iloc[0] == 0.7188
        assert quotes.gamma.iloc[0] == 0.0029
        assert quotes.theta.iloc[0] == -0.0403
        assert quotes.vega.iloc[0] == 1.3368


def test_get_options_quotes_response_200_dataframe_polars(
    load_json, respx_mock, client
):

    with patch(
        "marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY",
        ["polars"],
    ):
        mock_data = load_json("options_quotes_response_200")

        respx_mock.get(
            "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
        ).respond(
            json=mock_data,
            status_code=200,
        )
        quotes = client.options.quotes(
            symbols="AAPL271217C00255000", output_format=OutputFormat.DATAFRAME
        )
        assert "s" not in quotes.columns
        assert len(quotes) == 1
        assert quotes["optionSymbol"][0] == "AAPL271217C00255000"
        assert quotes["underlying"][0] == "AAPL"
        assert quotes["expiration"][0] == 1829077200
        assert quotes["side"][0] == "call"
        assert quotes["strike"][0] == 255
        assert quotes["firstTraded"][0] == 1741872600
        assert quotes["dte"][0] == 737
        assert quotes["updated"][0] == 1765396196
        assert quotes["bid"][0] == 65.1
        assert quotes["bidSize"][0] == 29
        assert quotes["mid"][0] == 65.75
        assert quotes["ask"][0] == 66.4
        assert quotes["askSize"][0] == 84
        assert quotes["openInterest"][0] == 588
        assert quotes["volume"][0] == 0
        assert quotes["inTheMoney"][0] == True
        assert quotes["intrinsicValue"][0] == 23.7344
        assert quotes["extrinsicValue"][0] == 42.0156
        assert quotes["underlyingPrice"][0] == 278.7344
        assert quotes["delta"][0] == 0.7188
        assert quotes["gamma"][0] == 0.0029
        assert quotes["theta"][0] == -0.0403
        assert quotes["vega"][0] == 1.3368


def test_get_options_quotes_response_400(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        json={},
        status_code=400,
    )

    result = client.options.quotes(
        symbols=["AAPL271217C00255000"], output_format=OutputFormat.INTERNAL
    )
    assert isinstance(result, MarketDataClientErrorResult)


def test_get_options_quotes_status_offline(respx_mock, client):
    mock_data = {
        "s": "ok",
        "service": ["/v1/options/quotes/"],
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

    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        json={},
        status_code=501,
    )

    quotes = client.options.quotes(
        symbols="AAPL271217C00255000", output_format=OutputFormat.INTERNAL
    )
    assert isinstance(quotes, MarketDataClientErrorResult)


def test_get_options_quotes_response_200_csv(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        text="AS RECEIVED FROM API",
        status_code=200,
    )
    output = client.options.quotes(
        symbols="AAPL271217C00255000",
        output_format=OutputFormat.CSV,
        filename="test.csv",
    )
    assert pathlib.Path(output).read_text() is not ""


def test_options_quotes_join_dicts():
    dicts = [
        {
            "s": "ok",
            "optionSymbol": ["AAPL271217C00255000"],
            "underlying": ["AAPL"],
            "expiration": [1829077200],
        },
        {
            "s": "ok",
            "optionSymbol": ["AAPL271217C00255000"],
            "underlying": ["AAPL"],
            "expiration": [1829077200],
        },
    ]
    joined = OptionsQuotes.join_dicts(dicts)
    assert joined["s"] == "ok"
    assert joined["optionSymbol"] == ["AAPL271217C00255000", "AAPL271217C00255000"]
    assert joined["underlying"] == ["AAPL", "AAPL"]
    assert joined["expiration"] == [1829077200, 1829077200]


def test_options_quotes_get_null_dict():
    null_dict = OptionsQuotes.get_null_dict()
    assert null_dict == {
        "optionSymbol": [],
        "underlying": [],
        "expiration": [],
        "side": [],
        "strike": [],
        "firstTraded": [],
        "dte": [],
        "updated": [],
        "bid": [],
        "bidSize": [],
        "mid": [],
        "last": [],
        "ask": [],
        "askSize": [],
        "openInterest": [],
        "volume": [],
        "inTheMoney": [],
        "intrinsicValue": [],
        "extrinsicValue": [],
        "underlyingPrice": [],
        "iv": [],
        "delta": [],
        "gamma": [],
        "theta": [],
        "vega": [],
    }


def test_options_quotes_get_null_csv_string():
    fields = list(OptionsQuotes.__dataclass_fields__.keys())
    null_csv_string = OptionsQuotes.get_null_csv_string()
    assert null_csv_string == ",".join([""] * len(fields))
    null_csv_string = OptionsQuotes.get_null_csv_string(add_headers=True)
    assert null_csv_string == ",".join(fields) + "\n" + ",".join([""] * len(fields))


def test_options_quotes_human_readable_join_dicts():
    dicts = [
        {
            "s": "ok",
            "Symbol": ["AAPL271217C00255000"],
            "Underlying": ["AAPL"],
            "Expiration Date": [1829077200],
        },
        {
            "s": "ok",
            "Symbol": ["AAPL271217C00255000"],
            "Underlying": ["AAPL"],
            "Expiration Date": [1829077200],
        },
    ]
    assert OptionsQuotesHumanReadable.join_dicts(dicts) == {
        "Symbol": ["AAPL271217C00255000", "AAPL271217C00255000"],
        "Underlying": ["AAPL", "AAPL"],
        "Expiration_Date": [1829077200, 1829077200],
    }


def test_options_quotes_human_readable_get_null_dict():
    null_dict = OptionsQuotesHumanReadable.get_null_dict()
    assert null_dict == {
        "Symbol": [],
        "Underlying": [],
        "Expiration Date": [],
        "Option Side": [],
        "Strike": [],
        "First Traded": [],
        "Days To Expiration": [],
        "Date": [],
        "Bid": [],
        "Bid Size": [],
        "Mid": [],
        "Ask": [],
        "Ask Size": [],
        "Last": [],
        "Open Interest": [],
        "Volume": [],
        "In The Money": [],
        "Intrinsic Value": [],
        "Extrinsic Value": [],
        "Underlying Price": [],
        "IV": [],
        "Delta": [],
        "Gamma": [],
        "Theta": [],
        "Vega": [],
    }


def test_options_quotes_human_readable_get_null_csv_string():
    fields = list(OptionsQuotesHumanReadable.__dataclass_fields__.keys())
    null_csv_string = OptionsQuotesHumanReadable.get_null_csv_string()
    assert null_csv_string == ",".join([""] * len(fields))
    null_csv_string = OptionsQuotesHumanReadable.get_null_csv_string(add_headers=True)
    expected_csv_string = (
        ",".join([field.replace("_", " ") for field in fields])
        + "\n"
        + ",".join([""] * len(fields)).replace("_", " ")
    )
    assert null_csv_string == expected_csv_string
