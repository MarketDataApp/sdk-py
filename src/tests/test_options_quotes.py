import datetime
import pathlib
from unittest.mock import patch

import pytest
import pytz

from marketdata.exceptions import (
    BadRequestError,
    MarketdataHttpError,
    MinMaxDateValidationError,
    NotFoundError,
    ParseError,
    ServerError,
)
from marketdata.input_types.base import OutputFormat
from marketdata.input_types.options import OptionsQuotesInput
from marketdata.output_types.options_quotes import (
    OptionsQuotes,
    OptionsQuotesHumanReadable,
)


def test_options_quotes_str():
    timestamp = int(
        datetime.datetime(
            2025, 1, 1, 0, 0, 0, 0, pytz.timezone("US/Eastern")
        ).timestamp()
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
        datetime.datetime(
            2025, 1, 1, 0, 0, 0, 0, pytz.timezone("US/Eastern")
        ).timestamp()
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
    expected = datetime.datetime(
        2025, 12, 10, 19, 49, 56, tzinfo=datetime.timezone.utc
    ).astimezone(pytz.timezone("US/Eastern"))
    assert quotes.updated[0].astimezone(pytz.timezone("US/Eastern")) == expected
    assert quotes.bid[0] == 65.1
    assert quotes.bidSize[0] == 29
    assert quotes.mid[0] == 65.75
    assert quotes.ask[0] == 66.4
    assert quotes.askSize[0] == 84
    assert quotes.last[0] == 64.97
    assert quotes.openInterest[0] == 588
    assert quotes.volume[0] == 0
    assert quotes.inTheMoney[0]
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
    assert quotes.Expiration_Date[0] == datetime.datetime.fromtimestamp(
        1829077200, tz=pytz.timezone("US/Eastern")
    )
    assert quotes.Option_Side[0] == "call"
    assert quotes.Strike[0] == 250
    assert quotes.First_Traded[0] == datetime.datetime.fromtimestamp(
        1741872600, tz=pytz.timezone("US/Eastern")
    )
    assert quotes.Days_To_Expiration[0] == 735
    assert quotes.Date[0] == datetime.datetime.fromtimestamp(
        1765562189, tz=pytz.timezone("US/Eastern")
    )
    assert quotes.Bid[0] == 67.05
    assert quotes.Bid_Size[0] == 337
    assert quotes.Mid[0] == 68.18
    assert quotes.Ask[0] == 69.3
    assert quotes.Ask_Size[0] == 365
    assert quotes.Last[0] == 67.46
    assert quotes.Open_Interest[0] == 5094
    assert quotes.Volume[0] == 10
    assert quotes.In_The_Money[0]
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


@pytest.mark.parametrize(
    "output_format", [OutputFormat.INTERNAL, OutputFormat.JSON, OutputFormat.DATAFRAME]
)
@pytest.mark.parametrize("use_human_readable", [False, True])
@pytest.mark.parametrize("bad_first", [False, True])
def test_options_quotes_undecodable_symbol_body_is_a_parse_error(
    load_json, respx_mock, client, output_format, use_human_readable, bad_first
):
    """Issue #82: a symbol answering 200 with a body that is not JSON (a proxy
    or a captive portal error page) fails the call as every other resource
    does, instead of being swapped for a fabricated empty row that read as
    "no options" and broke the merge of the healthy symbols."""
    fixture = (
        "options_quotes_human_response_200"
        if use_human_readable
        else "options_quotes_response_200"
    )
    good = respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(json=load_json(fixture), status_code=200)
    bad = respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217P00255000/"
    ).respond(text="<html>error page</html>", status_code=200)
    symbols = ["AAPL271217C00255000", "AAPL271217P00255000"]
    if bad_first:
        symbols.reverse()

    with pytest.raises(ParseError) as exc_info:
        client.options.quotes(
            symbols=symbols,
            output_format=output_format,
            use_human_readable=use_human_readable,
        )

    error = exc_info.value
    assert error.status_code == 200
    assert error.request_url.startswith(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217P00255000/"
    )
    assert "<html>error page</html>" in error.message
    assert good.call_count == 1
    assert bad.call_count == 1


def test_options_quotes_empty_symbol_body_is_a_parse_error(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        text="",
        status_code=200,
    )

    with pytest.raises(ParseError):
        client.options.quotes(
            symbols="AAPL271217C00255000", output_format=OutputFormat.INTERNAL
        )


def test_options_quotes_no_one_good_status_code(respx_mock, client):
    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(
        json={
            "s": "error",
        },
        status_code=205,
    )

    with pytest.raises(MarketdataHttpError) as exc_info:
        client.options.quotes(
            symbols="AAPL271217C00255000", output_format=OutputFormat.INTERNAL
        )
    assert exc_info.value.message == "No responses from API"


# ------------------------------------------------- merging the JSON answers

THIRD_URL = "https://api.marketdata.app/v1/options/quotes/AAPL271217C00260000/"
THREE_SYMBOLS = ["AAPL271217C00255000", "AAPL271217P00255000", "AAPL271217C00260000"]


def _answer_three_symbols(respx_mock, first: dict, second: dict, third: dict):
    for url, body in ((CALL_URL, first), (PUT_URL, second), (THIRD_URL, third)):
        respx_mock.get(url).respond(json=body, status_code=200)


@pytest.mark.parametrize(
    "output_format", [OutputFormat.DATAFRAME, OutputFormat.JSON, OutputFormat.INTERNAL]
)
@pytest.mark.parametrize(
    ("use_human_readable", "symbol_key", "bid_key"),
    [(False, "optionSymbol", "bid"), (True, "Symbol", "Bid")],
)
@pytest.mark.parametrize("lacking", [1, 0], ids=["second-symbol", "first-symbol"])
def test_options_quotes_symbol_missing_a_column_is_a_parse_error(
    respx_mock, client, output_format, use_human_readable, symbol_key, bid_key, lacking
):
    """The review of #92: one symbol's answer lacks the bid. The merge padded
    that column with nothing, so the third symbol's bid landed on the second
    symbol's row, and the human-readable merge raised a bare `KeyError`; when
    the first symbol was the one lacking it, the bid vanished for every
    symbol without a word. Any answer lacking a column another one carries
    now fails the call naming that symbol, the rule the chunks of
    `stocks.candles` follow (#90). The answers have the shape the API gives
    under `columns=`: the requested keys only."""
    answers = [
        {symbol_key: [name], bid_key: [price]}
        for name, price in (("A", 1.0), ("B", 2.0), ("C", 3.0))
    ]
    del answers[lacking][bid_key]
    _answer_three_symbols(respx_mock, *answers)

    with pytest.raises(ParseError) as exc_info:
        client.options.quotes(
            symbols=THREE_SYMBOLS,
            output_format=output_format,
            use_human_readable=use_human_readable,
            columns=["optionSymbol", "bid"],
        )

    assert exc_info.value.request_url.startswith((CALL_URL, PUT_URL)[lacking])
    assert f"missing columns {[bid_key]!r}" in exc_info.value.message


@pytest.mark.parametrize(
    ("bid", "reason"),
    [([], "different lengths"), ("2.5", "are not lists"), (None, "are not lists")],
    ids=["empty", "a-string", "null"],
)
def test_options_quotes_symbol_with_a_broken_column_is_a_parse_error(
    respx_mock, client, bid, reason
):
    """A column that is there but empty, or not a list, shifts the rows the
    same way: an empty bid put the third symbol's bid on the second symbol's
    row, and a string was split into its characters."""
    _answer_three_symbols(
        respx_mock,
        {"optionSymbol": ["A"], "bid": [1.0]},
        {"optionSymbol": ["B"], "bid": bid},
        {"optionSymbol": ["C"], "bid": [3.0]},
    )

    with pytest.raises(ParseError) as exc_info:
        client.options.quotes(
            symbols=THREE_SYMBOLS,
            output_format=OutputFormat.JSON,
            columns=["optionSymbol", "bid"],
        )

    assert exc_info.value.request_url.startswith(PUT_URL)
    assert reason in exc_info.value.message


def test_options_quotes_keeps_the_order_the_columns_were_requested_in(
    respx_mock, client
):
    """Checked live: under `columns=bid,optionSymbol` the API answers
    `{"bid": [...], "optionSymbol": [...]}`, in request order and with no
    status flag. The merge keeps that order, which is the order of the empty
    result (#87) and of every single-request resource; the flag the SDK adds
    comes after the columns, where it always went for such an answer."""
    _answer_three_symbols(
        respx_mock,
        *[
            {"bid": [price], "optionSymbol": [name]}
            for name, price in (("A", 1.0), ("B", 2.0), ("C", 3.0))
        ],
    )

    result = client.options.quotes(
        symbols=THREE_SYMBOLS,
        output_format=OutputFormat.JSON,
        columns=["bid", "optionSymbol"],
    )

    assert list(result) == ["bid", "optionSymbol", "s"]
    assert result["bid"] == [1.0, 2.0, 3.0]


def test_options_quotes_merges_the_requested_columns_row_by_row(respx_mock, client):
    _answer_three_symbols(
        respx_mock,
        {"s": "ok", "optionSymbol": ["A"], "bid": [1.0]},
        {"s": "ok", "optionSymbol": ["B"], "bid": [2.0]},
        {"s": "ok", "optionSymbol": ["C"], "bid": [3.0]},
    )

    with patch("marketdata.output_handlers.DATAFRAME_HANDLERS_PRIORITY", ["pandas"]):
        frame = client.options.quotes(
            symbols=THREE_SYMBOLS,
            output_format=OutputFormat.DATAFRAME,
            columns=["optionSymbol", "bid"],
        )

    assert frame["bid"].to_dict() == {"A": 1.0, "B": 2.0, "C": 3.0}


@pytest.mark.parametrize(
    "body", ["null", "[]", '"ok"'], ids=["null", "array", "string"]
)
@pytest.mark.parametrize("use_human_readable", [False, True])
def test_options_quotes_symbol_answering_a_json_non_object_is_a_parse_error(
    load_json, respx_mock, client, body, use_human_readable
):
    """A body that decodes to something other than an object used to fail
    with an `AttributeError` from inside the merge."""
    fixture = (
        "options_quotes_human_response_200"
        if use_human_readable
        else "options_quotes_response_200"
    )
    respx_mock.get(CALL_URL).respond(json=load_json(fixture), status_code=200)
    respx_mock.get(PUT_URL).respond(text=body, status_code=200)

    with pytest.raises(ParseError) as exc_info:
        client.options.quotes(
            symbols=THREE_SYMBOLS[:2],
            output_format=OutputFormat.JSON,
            use_human_readable=use_human_readable,
        )

    assert exc_info.value.request_url.startswith(PUT_URL)
    assert "not a JSON object" in exc_info.value.message


@pytest.mark.parametrize("use_human_readable", [False, True])
def test_options_quotes_answer_without_any_column_is_a_parse_error(
    respx_mock, client, use_human_readable
):
    """A JSON body with none of the resource's columns (a proxy's JSON error
    page) is not an answer of this resource. Merged, it gave a result with no
    rows, which reads as "no options" (#82)."""
    respx_mock.get(CALL_URL).respond(
        json={"s": "ok", "error": "upstream timeout"}, status_code=200
    )

    with pytest.raises(ParseError) as exc_info:
        client.options.quotes(
            symbols=THREE_SYMBOLS[0],
            output_format=OutputFormat.JSON,
            use_human_readable=use_human_readable,
        )

    assert "none of this resource's fields" in exc_info.value.message


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
        assert quotes.expiration.iloc[0] == datetime.datetime.fromtimestamp(
            1829077200, tz=pytz.timezone("US/Eastern")
        )
        assert quotes.side.iloc[0] == "call"
        assert quotes.strike.iloc[0] == 255
        assert quotes.firstTraded.iloc[0] == datetime.datetime.fromtimestamp(
            1741872600, tz=pytz.timezone("US/Eastern")
        )
        assert quotes.dte.iloc[0] == 737
        assert quotes.updated.iloc[0] == datetime.datetime.fromtimestamp(
            1765396196, tz=pytz.timezone("US/Eastern")
        )
        assert quotes.bid.iloc[0] == 65.1
        assert quotes.bidSize.iloc[0] == 29
        assert quotes.mid.iloc[0] == 65.75
        assert quotes.ask.iloc[0] == 66.4
        assert quotes.askSize.iloc[0] == 84
        assert quotes.openInterest.iloc[0] == 588
        assert quotes.volume.iloc[0] == 0
        assert quotes.inTheMoney.iloc[0]
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
        assert quotes["expiration"][0] == datetime.datetime.fromtimestamp(
            1829077200, tz=pytz.timezone("US/Eastern")
        )
        assert quotes["side"][0] == "call"
        assert quotes["strike"][0] == 255
        assert quotes["firstTraded"][0] == datetime.datetime.fromtimestamp(
            1741872600, tz=pytz.timezone("US/Eastern")
        )
        assert quotes["dte"][0] == 737
        assert quotes["updated"][0] == datetime.datetime.fromtimestamp(
            1765396196, tz=pytz.timezone("US/Eastern")
        )
        assert quotes["bid"][0] == 65.1
        assert quotes["bidSize"][0] == 29
        assert quotes["mid"][0] == 65.75
        assert quotes["ask"][0] == 66.4
        assert quotes["askSize"][0] == 84
        assert quotes["openInterest"][0] == 588
        assert quotes["volume"][0] == 0
        assert quotes["inTheMoney"][0]
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

    with pytest.raises(BadRequestError):
        client.options.quotes(
            symbols=["AAPL271217C00255000"], output_format=OutputFormat.INTERNAL
        )


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

    with pytest.raises(ServerError):
        client.options.quotes(
            symbols="AAPL271217C00255000", output_format=OutputFormat.INTERNAL
        )


# ------------------------------------------------------------------- CSV

CALL_URL = "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
PUT_URL = "https://api.marketdata.app/v1/options/quotes/AAPL271217P00255000/"
CSV_HEADER = (
    "optionSymbol,underlying,expiration,side,strike,firstTraded,dte,updated,bid,"
    "bidSize,mid,ask,askSize,last,openInterest,volume,inTheMoney,intrinsicValue,"
    "extrinsicValue,underlyingPrice,iv,delta,gamma,theta,vega"
)
CALL_ROW = (
    "AAPL271217C00255000,AAPL,1828818000,call,255,1686663000,822,1765396196,65.1,"
    "29,65.75,66.4,84,64.97,588,0,true,23.7344,42.0156,278.7344,0.2975,0.7188,"
    "0.0029,-0.0403,1.3368"
)
PUT_ROW = CALL_ROW.replace("AAPL271217C00255000", "AAPL271217P00255000").replace(
    ",call,", ",put,"
)
CSV_PLACEHOLDER = '0\r\n""\r\n'


def test_get_options_quotes_response_200_csv(respx_mock, client, tmp_path):
    """The file is the API's CSV as received: its header, its rows."""
    respx_mock.get(CALL_URL).respond(
        text=f"{CSV_HEADER}\r\n{CALL_ROW}\r\n", status_code=200
    )

    output = client.options.quotes(
        symbols="AAPL271217C00255000",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
    )

    assert pathlib.Path(output).read_bytes() == (
        f"{CSV_HEADER}\r\n{CALL_ROW}\r\n".encode()
    )


def test_options_quotes_csv_merges_every_symbol_under_the_api_header(
    respx_mock, client, tmp_path
):
    respx_mock.get(CALL_URL).respond(text=f"{CSV_HEADER}\n{CALL_ROW}\n")
    respx_mock.get(PUT_URL).respond(text=f"{CSV_HEADER}\n{PUT_ROW}\n")

    output = client.options.quotes(
        symbols=["AAPL271217C00255000", "AAPL271217P00255000"],
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
    )

    assert pathlib.Path(output).read_bytes() == (
        f"{CSV_HEADER}\r\n{CALL_ROW}\r\n{PUT_ROW}\r\n".encode()
    )


def test_options_quotes_csv_keeps_the_requested_columns(respx_mock, client, tmp_path):
    """Issue #86: under `columns=` the API answers with the requested columns
    only; the merge used to drop every row because the header did not match
    the model's field list."""
    respx_mock.get(CALL_URL).respond(
        text="optionSymbol,bid,ask\r\nAAPL271217C00255000,85.25,87.95\r\n"
    )
    respx_mock.get(PUT_URL).respond(
        text="optionSymbol,bid,ask\r\nAAPL271217P00255000,1.1,1.2\r\n"
    )

    output = client.options.quotes(
        symbols=["AAPL271217C00255000", "AAPL271217P00255000"],
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
        columns=["optionSymbol", "bid", "ask"],
    )

    assert pathlib.Path(output).read_bytes() == (
        b"optionSymbol,bid,ask\r\n"
        b"AAPL271217C00255000,85.25,87.95\r\n"
        b"AAPL271217P00255000,1.1,1.2\r\n"
    )


def test_options_quotes_csv_keeps_the_human_readable_rows(respx_mock, client, tmp_path):
    """Issue #86: the human-readable header (`Symbol`, names with spaces)
    never matched the model's field list, so the file was header-only."""
    body = "Symbol,Underlying,Expiration Date,Bid,Ask\r\nAAPL271217C00255000,AAPL,1829077200,85.25,87.95\r\n"
    respx_mock.get(CALL_URL).respond(text=body)

    output = client.options.quotes(
        symbols="AAPL271217C00255000",
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
        use_human_readable=True,
    )

    assert pathlib.Path(output).read_bytes() == body.encode()


@pytest.mark.parametrize("use_human_readable", [False, True])
def test_options_quotes_csv_undecodable_symbol_body_is_a_parse_error(
    respx_mock, client, tmp_path, use_human_readable
):
    """Issue #86 (the CSV half of #82): an HTML page from one symbol fails the
    call instead of vanishing from the file."""
    good_body = (
        "Symbol,Bid,Ask\r\nAAPL271217C00255000,85.25,87.95\r\n"
        if use_human_readable
        else f"{CSV_HEADER}\r\n{CALL_ROW}\r\n"
    )
    respx_mock.get(CALL_URL).respond(text=good_body)
    respx_mock.get(PUT_URL).respond(text="<html>error page</html>")

    with pytest.raises(ParseError) as exc_info:
        client.options.quotes(
            symbols=["AAPL271217C00255000", "AAPL271217P00255000"],
            output_format=OutputFormat.CSV,
            filename=tmp_path / "test.csv",
            use_human_readable=use_human_readable,
        )

    assert exc_info.value.request_url.startswith(PUT_URL)
    assert not (tmp_path / "test.csv").exists()


def test_options_quotes_csv_leaves_out_a_symbol_with_no_data(
    respx_mock, client, tmp_path
):
    """Issue #89: the API's CSV placeholder for an empty symbol is a 200; it
    must be skipped like a JSON 404 no_data, not merged, not an error."""
    respx_mock.get(CALL_URL).respond(text=f"{CSV_HEADER}\r\n{CALL_ROW}\r\n")
    respx_mock.get(PUT_URL).respond(text=CSV_PLACEHOLDER)

    output = client.options.quotes(
        symbols=["AAPL271217C00255000", "AAPL271217P00255000"],
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
    )

    assert pathlib.Path(output).read_bytes() == (
        f"{CSV_HEADER}\r\n{CALL_ROW}\r\n".encode()
    )


def test_options_quotes_csv_with_every_symbol_empty_is_a_header_only_file(
    respx_mock, client, tmp_path
):
    respx_mock.get(CALL_URL).respond(text=CSV_PLACEHOLDER)
    respx_mock.get(PUT_URL).respond(text=CSV_PLACEHOLDER)

    output = client.options.quotes(
        symbols=["AAPL271217C00255000", "AAPL271217P00255000"],
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
    )

    assert pathlib.Path(output).read_bytes() == f"{CSV_HEADER}\r\n".encode()


@pytest.mark.parametrize(
    ("output_format", "answer"),
    [
        (
            OutputFormat.JSON,
            {"json": {"s": "error", "errmsg": "No option found."}},
        ),
        (OutputFormat.CSV, {"text": "s,errmsg\r\nerror,No option found.\r\n"}),
    ],
    ids=["json", "csv"],
)
def test_options_quotes_one_unknown_symbol_fails_the_call_on_every_format(
    respx_mock, client, tmp_path, output_format, answer
):
    """A symbol the API answers with a message (an expired or misspelled
    contract) fails the whole call, as it already did on JSON output: it is a
    404 with an `errmsg`, not the empty answer (#91). Only a symbol with no
    message contributes no rows and lets the others through."""
    respx_mock.get(CALL_URL).respond(text=f"{CSV_HEADER}\r\n{CALL_ROW}\r\n")
    respx_mock.get(PUT_URL).respond(status_code=404, **answer)

    with pytest.raises(NotFoundError):
        client.options.quotes(
            symbols=["AAPL271217C00255000", "AAPL271217P00255000"],
            output_format=output_format,
            filename=tmp_path / "test.csv",
        )

    assert not (tmp_path / "test.csv").exists()


def test_options_quotes_csv_without_headers_and_every_symbol_empty_is_an_empty_file(
    respx_mock, client, tmp_path
):
    """Under `add_headers=False` the API's placeholder is the lone empty cell,
    and the empty file must not gain a header the caller declined."""
    respx_mock.get(CALL_URL).respond(text='""\r\n')
    respx_mock.get(PUT_URL).respond(text='""\r\n')

    output = client.options.quotes(
        symbols=["AAPL271217C00255000", "AAPL271217P00255000"],
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
        add_headers=False,
    )

    assert pathlib.Path(output).read_bytes() == b""


def test_options_quotes_csv_without_headers_concatenates_the_rows(
    respx_mock, client, tmp_path
):
    respx_mock.get(CALL_URL).respond(text=f"{CALL_ROW}\r\n")
    respx_mock.get(PUT_URL).respond(text=f"{PUT_ROW}\r\n")

    output = client.options.quotes(
        symbols=["AAPL271217C00255000", "AAPL271217P00255000"],
        output_format=OutputFormat.CSV,
        filename=tmp_path / "test.csv",
        add_headers=False,
    )

    assert pathlib.Path(output).read_bytes() == (
        f"{CALL_ROW}\r\n{PUT_ROW}\r\n".encode()
    )


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
    assert list(joined)[0] == "s"
    assert joined["s"] == "ok"
    assert joined["optionSymbol"] == ["AAPL271217C00255000", "AAPL271217C00255000"]
    assert joined["underlying"] == ["AAPL", "AAPL"]
    # `join_dicts` concatenates the raw values; the timestamps become datetimes
    # in `__post_init__`, which this test does not reach.
    assert joined["expiration"] == [1829077200, 1829077200]


def test_options_quotes_human_readable_join_dicts():
    """The human-readable merge, the only place the API's spaced names are
    translated to the model's underscored ones. It went out of this PR with
    the null helpers by mistake: nothing else exercises it with more than one
    symbol, so a `join_dicts` that kept only the first symbol's rows would
    leave the suite green and the file at 100% coverage."""
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


@pytest.mark.parametrize(
    ("model", "dicts"),
    [
        (
            OptionsQuotes,
            [{"s": "ok", "optionSymbol": ["A"], "bid": [1.0]}, {"optionSymbol": ["B"]}],
        ),
        (
            OptionsQuotesHumanReadable,
            [{"Symbol": ["A"], "Bid": [1.0]}, {"Symbol": ["B"]}],
        ),
    ],
)
def test_options_quotes_join_dicts_refuses_to_shift_the_rows(model, dicts):
    """Called on its own, a merge that cannot line the rows up raises rather
    than padding the missing column with nothing. The API-named merge used to
    pad it; the human-readable one already raised, and is pinned here so the
    two keep agreeing."""
    with pytest.raises(KeyError):
        model.join_dicts(dicts)


def test_options_quotes_join_dicts_follows_the_keys_it_is_given():
    """`quotes()` hands over the columns it checked, in the order the API sent
    them. Under `columns=` the API sends no status flag, and the one the SDK
    adds goes after the columns, where the merge always put it for such an
    answer; an answer that carries the flag keeps it first."""
    filtered = [
        {"bid": [1.0], "optionSymbol": ["A"]},
        {"bid": [2.0], "optionSymbol": ["B"]},
    ]
    full = [{"s": "ok", **answer} for answer in filtered]

    joined = OptionsQuotes.join_dicts(filtered, ["bid", "optionSymbol"])

    assert list(joined) == ["bid", "optionSymbol", "s"]
    assert joined == {"bid": [1.0, 2.0], "optionSymbol": ["A", "B"], "s": "ok"}
    assert list(OptionsQuotes.join_dicts(full, ["bid", "optionSymbol"])) == [
        "s",
        "bid",
        "optionSymbol",
    ]


def test_options_quotes_answer_keys_are_the_keys_the_api_sends(load_json):
    """The one naming rule behind both the check and the merge: the API model's
    field names, and the human-readable names spelled with the API's spaces.
    Checked against real answers, so a key the API spells differently from the
    rule shows up here rather than as a rejected symbol."""
    api_answer = load_json("options_quotes_response_200")
    human_answer = load_json("options_quotes_human_response_200")

    assert OptionsQuotes.answer_keys() == [key for key in api_answer if key != "s"]
    assert OptionsQuotesHumanReadable.answer_keys() == list(human_answer)


def test_options_quotes_input_date_range_aliases_on_wire(load_json, respx_mock, client):
    mock_data = load_json("options_quotes_response_200")
    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(json=mock_data, status_code=200)

    client.options.quotes(
        symbols="AAPL271217C00255000",
        from_date="2026-04-14",
        to_date="2026-04-18",
        output_format=OutputFormat.INTERNAL,
    )

    params = respx_mock.calls.last.request.url.params
    assert params.get("from") == "2026-04-14"
    assert params.get("to") == "2026-04-18"
    assert params.get("from_date") is None
    assert params.get("to_date") is None


def test_options_quotes_input_date_param_on_wire(load_json, respx_mock, client):
    mock_data = load_json("options_quotes_response_200")
    respx_mock.get(
        "https://api.marketdata.app/v1/options/quotes/AAPL271217C00255000/"
    ).respond(json=mock_data, status_code=200)

    client.options.quotes(
        symbols="AAPL271217C00255000",
        date="2026-04-15",
        output_format=OutputFormat.INTERNAL,
    )

    params = respx_mock.calls.last.request.url.params
    assert params.get("date") == "2026-04-15"


def test_options_quotes_input_from_after_to_raises():
    with pytest.raises(MinMaxDateValidationError):
        OptionsQuotesInput(
            symbols="AAPL271217C00255000",
            from_date=datetime.date(2026, 4, 18),
            to_date=datetime.date(2026, 4, 14),
        )
