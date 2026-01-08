# Stocks Resource

The `stocks` resource provides access to stock market data, including real-time prices, quotes, historical candles (OHLCV data), earnings information, and news articles.

## Accessing the Stocks Resource

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
stocks = client.stocks
```

All methods in the stocks resource include API status checking and automatic retry logic. See the [README](../README.md) for general information about error handling, retry mechanisms, and output formats.

## Methods

### `prices()`

Fetches stock prices for one or more symbols. This method includes API status checking and automatic retry logic.

> **Note:** The `symbols` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbols` (str | list[str]): A single stock symbol (e.g., "AAPL") or a list of symbols (e.g., ["AAPL", "GOOGL", "MSFT"])
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns a list of `StockPrice` objects
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string
- `date_format` (DateFormat, optional): The date format to use. Defaults to `DateFormat.UNIX`.
  - `DateFormat.TIMESTAMP`: ISO timestamp format
  - `DateFormat.UNIX`: Unix timestamp (seconds since epoch)
  - `DateFormat.SPREADSHEET`: Spreadsheet-compatible format
- `columns` (list[str], optional): List of column names to include in the response
- `add_headers` (bool, optional): Whether to add headers to the response
- `use_human_readable` (bool, optional): Whether to use human-readable format
- `mode` (Mode, optional): The data feed mode to use (`Mode.LIVE`, `Mode.CACHED`, `Mode.DELAYED`)
- `filename` (str | Path, optional): File path for CSV output (only used with `output_format=OutputFormat.CSV`). Must end with `.csv`, directory must exist, and file must not already exist. If not provided, a timestamped file is created in `output/` directory (the directory is automatically created if it doesn't exist).

#### Returns

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with stock price data (indexed by symbol). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `symbol` column if present
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: A list of `StockPrice` objects (or `StockPricesHumanReadable` if `use_human_readable=True`)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get prices for a single symbol (DataFrame):**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
df = client.stocks.prices("AAPL")
# or
df = client.stocks.prices(symbols="AAPL")
print(df)
```

**Get prices for multiple symbols:**

```python
# symbols can be passed positionally or as keyword argument
df = client.stocks.prices(["AAPL", "GOOGL", "MSFT"])
# or
df = client.stocks.prices(symbols=["AAPL", "GOOGL", "MSFT"])
print(df)
```

**Get prices as internal objects:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
prices = client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)
# or
prices = client.stocks.prices(symbols="AAPL", output_format=OutputFormat.INTERNAL)

for price in prices:
    print(f"{price.symbol}: ${price.mid} ({price.change_percent}%)")
```

**Get prices as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
json_data = client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.stocks.prices(symbols="AAPL", output_format=OutputFormat.JSON)
print(json_data)
```

**Get prices as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.stocks.prices("AAPL", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.stocks.prices(
    "AAPL", 
    output_format=OutputFormat.CSV,
    filename=Path("data/aapl_prices.csv")
)
if csv_file:
    print(f"CSV saved to: {csv_file}")
```

**Using universal parameters:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import DateFormat, Mode

client = MarketDataClient()
# Use custom date format and mode
df = client.stocks.prices(
    "AAPL",
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["symbol", "mid", "change_percent"]
)
```

### `quotes()`

Fetches stock quotes for one or more symbols. This method includes API status checking and automatic retry logic.

> **Note:** The `symbols` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbols` (str | list[str]): A single stock symbol (e.g., "AAPL") or a list of symbols (e.g., ["AAPL", "GOOGL", "MSFT"])
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns a list of `StockQuote` or `StockQuotesHumanReadable` objects
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string
- `use_52_week` (bool, optional): Whether to use the 52 week high and low
- `extended` (bool, optional): Whether to use the extended quotes
- `date_format` (DateFormat, optional): The date format to use. Defaults to `DateFormat.UNIX`.
  - `DateFormat.TIMESTAMP`: ISO timestamp format
  - `DateFormat.UNIX`: Unix timestamp (seconds since epoch)
  - `DateFormat.SPREADSHEET`: Spreadsheet-compatible format
- `columns` (list[str], optional): List of column names to include in the response
- `add_headers` (bool, optional): Whether to add headers to the response
- `use_human_readable` (bool, optional): Whether to use human-readable format
- `mode` (Mode, optional): The data feed mode to use (`Mode.LIVE`, `Mode.CACHED`, `Mode.DELAYED`)
- `filename` (str | Path, optional): File path for CSV output (only used with `output_format=OutputFormat.CSV`). Must end with `.csv`, directory must exist, and file must not already exist. If not provided, a timestamped file is created in `output/` directory (the directory is automatically created if it doesn't exist).

#### Returns

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with stock quotes data (indexed by symbol). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `symbol` column if present (or `Symbol` if human-readable)
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: A list of `StockQuote` objects (or `StockQuotesHumanReadable` if `use_human_readable=True`)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get quotes for a single symbol (DataFrame):**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
df = client.stocks.quotes("AAPL")
# or
df = client.stocks.quotes(symbols="AAPL")
print(df)
```

**Get quotes for multiple symbols:**

```python
# symbols can be passed positionally or as keyword argument
df = client.stocks.quotes(["AAPL", "GOOGL", "MSFT"])
# or
df = client.stocks.quotes(symbols=["AAPL", "GOOGL", "MSFT"])
print(df)
```

**Get quotes as internal objects:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
quotes = client.stocks.quotes("AAPL", output_format=OutputFormat.INTERNAL)
# or
quotes = client.stocks.quotes(symbols="AAPL", output_format=OutputFormat.INTERNAL)

for quote in quotes:
    print(f"{quote.symbol}: Bid ${quote.bid} / Ask ${quote.ask}")
    print(f"Mid: ${quote.mid}, Last: ${quote.last}")
    print(f"Change: ${quote.change} ({quote.change_percent}%)")
    print(f"Volume: {quote.volume}")
```

**Get quotes with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Symbol, Ask, Bid, Mid, Last, Change_Price, Change_Percent, Volume, Date
quotes = client.stocks.quotes(
    "AAPL",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

for quote in quotes:
    print(f"{quote.Symbol}: Bid ${quote.Bid} / Ask ${quote.Ask}")
    print(f"Mid: ${quote.Mid}, Last: ${quote.Last}")
    print(f"Change: ${quote.Change_Price} ({quote.Change_Percent}%)")
    print(f"Volume: {quote.Volume}")
```

**Get quotes as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
json_data = client.stocks.quotes("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.stocks.quotes(symbols="AAPL", output_format=OutputFormat.JSON)
print(json_data)
```

**Get quotes as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.stocks.quotes("AAPL", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.stocks.quotes(
    "AAPL", 
    output_format=OutputFormat.CSV,
    filename=Path("data/aapl_quotes.csv")
)
if csv_file:
    print(f"CSV saved to: {csv_file}")
```

**Using universal parameters:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import DateFormat, Mode

client = MarketDataClient()
# Use custom date format and mode
df = client.stocks.quotes(
    "AAPL",
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["symbol", "bid", "ask", "mid", "volume"]
)
```

**Using extended quotes:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get extended quotes
df = client.stocks.quotes("AAPL", extended=True)
print(df)
```

**Using 52-week data:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get quotes with 52-week high/low
df = client.stocks.quotes("AAPL", use_52_week=True)
print(df)
```

### `candles()`

Fetches stock candles (OHLCV data) for a symbol with support for various timeframes and date ranges. This method includes API status checking and automatic retry logic. For intraday resolutions (minutely/hourly), large date ranges are automatically split into year-long chunks and fetched concurrently using up to 50 concurrent requests.

> **Note:** The `symbol` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbol` (str): A single stock symbol (e.g., "AAPL")
- `resolution` (str, optional): The timeframe resolution for candles. Defaults to `"D"` (daily). Valid formats:
  - Numeric with unit: `"1"`, `"15M"`, `"1H"`, `"1D"`, `"1W"`, `"1M"`, `"1Y"`
  - Unit only: `"M"`, `"H"`, `"D"`, `"W"`, `"M"`, `"Y"`
  - Descriptive: `"minutely"`, `"hourly"`, `"daily"`, `"weekly"`, `"monthly"`, `"yearly"`
- `from_date` (datetime.date, optional): The start date to fetch candles for. When both `from_date` and `to_date` are provided, the date range is automatically split into year-long chunks and fetched concurrently for intraday resolutions (minutely/hourly) using up to 50 concurrent requests. For non-intraday resolutions (daily/weekly/monthly/yearly), the entire date range is fetched in a single request without splitting.
- `to_date` (datetime.date, optional): The end date to fetch candles for. When both `from_date` and `to_date` are provided, the date range is automatically split into year-long chunks and fetched concurrently for intraday resolutions (minutely/hourly) using up to 50 concurrent requests. For non-intraday resolutions (daily/weekly/monthly/yearly), the entire date range is fetched in a single request without splitting.
- `countback` (int, optional): The number of candles to fetch (alternative to date range)
- `extended` (bool, optional): Whether to fetch extended candles (pre-market and after-hours data)
- `adjust_splits` (bool, optional): Whether to adjust for stock splits. Uses API alias `adjustsplits`.
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns a list of `StockCandle` or `StockCandlesHumanReadable` objects
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string
- `date_format` (DateFormat, optional): The date format to use. Defaults to `DateFormat.UNIX`.
  - `DateFormat.TIMESTAMP`: ISO timestamp format
  - `DateFormat.UNIX`: Unix timestamp (seconds since epoch)
  - `DateFormat.SPREADSHEET`: Spreadsheet-compatible format
- `columns` (list[str], optional): List of column names to include in the response
- `add_headers` (bool, optional): Whether to add headers to the response
- `use_human_readable` (bool, optional): Whether to use human-readable format (uses `Date`, `Open`, `High`, `Low`, `Close`, `Volume` instead of `t`, `o`, `h`, `l`, `c`, `v`)
- `mode` (Mode, optional): The data feed mode to use (`Mode.LIVE`, `Mode.CACHED`, `Mode.DELAYED`)
- `filename` (str | Path, optional): File path for CSV output (only used with `output_format=OutputFormat.CSV`). Must end with `.csv`, directory must exist, and file must not already exist. If not provided, a timestamped file is created in `output/` directory (the directory is automatically created if it doesn't exist).

#### Returns

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with candle data (indexed by timestamp/Date). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `t` column (timestamp) or `Date` column (if human-readable)
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: A list of `StockCandle` objects (or `StockCandlesHumanReadable` if `use_human_readable=True`)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API (merged from multiple concurrent requests if date range spans multiple years for intraday resolutions)
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written (merged from multiple concurrent requests if date range spans multiple years for intraday resolutions)
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, no responses received, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`. If no valid responses are received from concurrent requests, a `MarketDataClientErrorResult` is returned.

#### Date Range Handling

When both `from_date` and `to_date` are provided, the method behavior depends on the resolution:

- **For intraday resolutions (minutely/hourly)**: The date range is automatically split into year-long chunks, fetched concurrently using a thread pool executor (up to 50 concurrent requests), and merged into a single response. This allows efficient fetching of large historical date ranges without manual pagination.

- **For non-intraday resolutions (daily/weekly/monthly/yearly)**: The entire date range is fetched in a single request without splitting.

#### Examples

**Get daily candles for a symbol (DataFrame):**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.stocks.candles("AAPL")
# or
df = client.stocks.candles(symbol="AAPL")
print(df)
```

**Get candles with specific resolution:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get hourly candles
df = client.stocks.candles("AAPL", resolution="1H")
# Get 15-minute candles
df = client.stocks.candles("AAPL", resolution="15M")
# Get weekly candles
df = client.stocks.candles("AAPL", resolution="W")
```

**Get candles for a date range:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Fetch candles for a specific date range
# Note: For daily/weekly/monthly/yearly resolutions, the entire range is fetched in one request
# For intraday resolutions (minutely/hourly), the range is automatically split into year-long chunks
df = client.stocks.candles(
    "AAPL",
    resolution="D",
    from_date=datetime.date(2020, 1, 1),
    to_date=datetime.date(2022, 12, 31)
)
print(df)
```

**Get candles using countback:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get last 100 daily candles
df = client.stocks.candles("AAPL", resolution="D", countback=100)
print(df)
```

**Get candles as internal objects:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
candles = client.stocks.candles("AAPL", output_format=OutputFormat.INTERNAL)
# or
candles = client.stocks.candles(symbol="AAPL", output_format=OutputFormat.INTERNAL)

for candle in candles:
    print(f"Time: {candle.t}")
    print(f"Open: {candle.o}, High: {candle.h}, Low: {candle.l}, Close: {candle.c}")
    print(f"Volume: {candle.v}")
```

**Get candles with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Date, Open, High, Low, Close, Volume instead of t, o, h, l, c, v
candles = client.stocks.candles(
    "AAPL",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

for candle in candles:
    print(f"Date: {candle.Date}")
    print(f"Open: {candle.Open}, High: {candle.High}, Low: {candle.Low}, Close: {candle.Close}")
    print(f"Volume: {candle.Volume}")
```

**Get candles as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
json_data = client.stocks.candles("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.stocks.candles(symbol="AAPL", output_format=OutputFormat.JSON)
print(json_data)
```

**Get candles as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.stocks.candles("AAPL", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.stocks.candles(
    "AAPL", 
    resolution="D",
    output_format=OutputFormat.CSV,
    filename=Path("data/aapl_candles.csv")
)
if csv_file:
    print(f"CSV saved to: {csv_file}")
```

**Using universal parameters:**

```python
import datetime
from marketdata.client import MarketDataClient
from marketdata.input_types.base import DateFormat, Mode

client = MarketDataClient()
# Use custom date format and mode
df = client.stocks.candles(
    "AAPL",
    resolution="D",
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31),
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["t", "o", "h", "l", "c", "v"]
)
```

**Using extended candles and split adjustment:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get extended candles (pre-market and after-hours) with split adjustment
df = client.stocks.candles(
    "AAPL",
    resolution="D",
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31),
    extended=True,
    adjust_splits=True
)
print(df)
```

### `earnings()`

Fetches earnings data for a symbol. This method includes API status checking and automatic retry logic.

> **Note:** The `symbol` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbol` (str): A single stock symbol (e.g., "AAPL")
- `from_date` (datetime.date, optional): The start date to fetch earnings for
- `to_date` (datetime.date, optional): The end date to fetch earnings for
- `countback` (int, optional): The number of earnings to fetch (alternative to date range)
- `date` (datetime.date, optional): The date to fetch earnings for
- `report_type` (str, optional): The type of earnings to fetch. Uses API alias `report`.
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns a `StockEarnings` or `StockEarningsHumanReadable` object
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string
- `date_format` (DateFormat, optional): The date format to use. Defaults to `DateFormat.UNIX`.
  - `DateFormat.TIMESTAMP`: ISO timestamp format
  - `DateFormat.UNIX`: Unix timestamp (seconds since epoch)
  - `DateFormat.SPREADSHEET`: Spreadsheet-compatible format
- `columns` (list[str], optional): List of column names to include in the response
- `add_headers` (bool, optional): Whether to add headers to the response
- `use_human_readable` (bool, optional): Whether to use human-readable format
- `mode` (Mode, optional): The data feed mode to use (`Mode.LIVE`, `Mode.CACHED`, `Mode.DELAYED`)
- `filename` (str | Path, optional): File path for CSV output (only used with `output_format=OutputFormat.CSV`). Must end with `.csv`, directory must exist, and file must not already exist. If not provided, a timestamped file is created in `output/` directory (the directory is automatically created if it doesn't exist).

#### Returns

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with earnings data (indexed by symbol). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `symbol` column if present (or `Symbol` if human-readable)
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: A `StockEarnings` object (or `StockEarningsHumanReadable` if `use_human_readable=True`)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get earnings for a symbol (DataFrame):**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.stocks.earnings("AAPL")
# or
df = client.stocks.earnings(symbol="AAPL")
print(df)
```

**Get earnings for a date range:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Fetch earnings for a specific date range
df = client.stocks.earnings(
    "AAPL",
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31)
)
print(df)
```

**Get earnings using countback:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get last 10 earnings reports
df = client.stocks.earnings("AAPL", countback=10)
print(df)
```

**Get earnings as internal objects:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
earnings = client.stocks.earnings("AAPL", output_format=OutputFormat.INTERNAL)
# or
earnings = client.stocks.earnings(symbol="AAPL", output_format=OutputFormat.INTERNAL)

print(f"Symbol: {earnings.symbol}")
print(f"Fiscal Year: {earnings.fiscalYear}")
print(f"Fiscal Quarter: {earnings.fiscalQuarter}")
print(f"Reported EPS: {earnings.reportedEPS}")
print(f"Estimated EPS: {earnings.estimatedEPS}")
```

**Get earnings with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Symbol, Fiscal_Year, Fiscal_Quarter, Reported_EPS, Estimated_EPS, etc.
earnings = client.stocks.earnings(
    "AAPL",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

print(f"Symbol: {earnings.Symbol}")
print(f"Fiscal Year: {earnings.Fiscal_Year}")
print(f"Fiscal Quarter: {earnings.Fiscal_Quarter}")
print(f"Reported EPS: {earnings.Reported_EPS}")
print(f"Estimated EPS: {earnings.Estimated_EPS}")
```

**Get earnings as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
json_data = client.stocks.earnings("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.stocks.earnings(symbol="AAPL", output_format=OutputFormat.JSON)
print(json_data)
```

**Get earnings as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.stocks.earnings("AAPL", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.stocks.earnings(
    "AAPL", 
    output_format=OutputFormat.CSV,
    filename=Path("data/aapl_earnings.csv")
)
if csv_file:
    print(f"CSV saved to: {csv_file}")
```

**Using universal parameters:**

```python
import datetime
from marketdata.client import MarketDataClient
from marketdata.input_types.base import DateFormat, Mode

client = MarketDataClient()
# Use custom date format and mode
df = client.stocks.earnings(
    "AAPL",
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31),
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["symbol", "fiscalYear", "fiscalQuarter", "reportedEPS", "estimatedEPS"]
)
```

### `news()`

Fetches news articles for a symbol. This method includes API status checking and automatic retry logic.

> **Note:** The `symbol` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbol` (str): A single stock symbol (e.g., "AAPL")
- `from_date` (datetime.date, optional): The start date to fetch news for
- `to_date` (datetime.date, optional): The end date to fetch news for
- `countback` (int, optional): The number of news articles to fetch (alternative to date range)
- `date` (datetime.date, optional): The date to fetch news for
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns a list of `StockNews` or `StockNewsHumanReadable` objects
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string
- `date_format` (DateFormat, optional): The date format to use. Defaults to `DateFormat.UNIX`.
  - `DateFormat.TIMESTAMP`: ISO timestamp format
  - `DateFormat.UNIX`: Unix timestamp (seconds since epoch)
  - `DateFormat.SPREADSHEET`: Spreadsheet-compatible format
- `columns` (list[str], optional): List of column names to include in the response
- `add_headers` (bool, optional): Whether to add headers to the response
- `use_human_readable` (bool, optional): Whether to use human-readable format
- `mode` (Mode, optional): The data feed mode to use (`Mode.LIVE`, `Mode.CACHED`, `Mode.DELAYED`)
- `filename` (str | Path, optional): File path for CSV output (only used with `output_format=OutputFormat.CSV`). Must end with `.csv`, directory must exist, and file must not already exist. If not provided, a timestamped file is created in `output/` directory (the directory is automatically created if it doesn't exist).

#### Returns

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with news data (indexed by symbol). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `symbol` column if present (or `Symbol` if human-readable)
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: A list of `StockNews` objects (or `StockNewsHumanReadable` if `use_human_readable=True`)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get news for a symbol (DataFrame):**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.stocks.news("AAPL")
# or
df = client.stocks.news(symbol="AAPL")
print(df)
```

**Get news for a date range:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Fetch news for a specific date range
df = client.stocks.news(
    "AAPL",
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31)
)
print(df)
```

**Get news using countback:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get last 50 news articles
df = client.stocks.news("AAPL", countback=50)
print(df)
```

**Get news as internal objects:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
news = client.stocks.news("AAPL", output_format=OutputFormat.INTERNAL)
# or
news = client.stocks.news(symbol="AAPL", output_format=OutputFormat.INTERNAL)

for article in news:
    print(f"Headline: {article.headline}")
    print(f"Source: {article.source}")
    print(f"Publication Date: {article.publicationDate}")
    print(f"Content: {article.content[:100]}...")
    print("---")
```

**Get news with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Symbol, Date instead of symbol, updated
news = client.stocks.news(
    "AAPL",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

for article in news:
    print(f"Headline: {article.headline}")
    print(f"Source: {article.source}")
    print(f"Publication Date: {article.publicationDate}")
    print(f"Date: {article.Date}")
    print(f"Content: {article.content[:100]}...")
    print("---")
```

**Get news as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
json_data = client.stocks.news("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.stocks.news(symbol="AAPL", output_format=OutputFormat.JSON)
print(json_data)
```

**Get news as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.stocks.news("AAPL", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.stocks.news(
    "AAPL", 
    output_format=OutputFormat.CSV,
    filename=Path("data/aapl_news.csv")
)
if csv_file:
    print(f"CSV saved to: {csv_file}")
```

**Using universal parameters:**

```python
import datetime
from marketdata.client import MarketDataClient
from marketdata.input_types.base import DateFormat, Mode

client = MarketDataClient()
# Use custom date format and mode
df = client.stocks.news(
    "AAPL",
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31),
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["symbol", "headline", "source", "publicationDate"]
)
```

## StockPrice Object

When using `OutputFormat.INTERNAL`, the `prices()` method returns a list of `StockPrice` objects (or `StockPricesHumanReadable` if `use_human_readable=True`) with the following properties:

### StockPrice Properties

- `symbol` (str): Stock symbol (e.g., "AAPL")
- `mid` (float): Mid price
- `change` (float): Price change
- `change_percent` (property): Alias for `changepct` - percentage change
- `changepct` (float): Percentage change (raw field name)
- `s` (str): Status string
- `updated` (datetime.datetime): Last update timestamp

### StockPricesHumanReadable Properties

When `use_human_readable=True`:
- `Symbol` (str): Stock symbol (e.g., "AAPL")
- `Mid` (float): Mid price
- `Change_Price` (float): Price change
- `Change_Percent` (float): Percentage change
- `Date` (datetime.datetime): Last update timestamp

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
prices = client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)
# or
prices = client.stocks.prices(symbols="AAPL", output_format=OutputFormat.INTERNAL)

for price in prices:
    print(f"Symbol: {price.symbol}")
    print(f"Mid Price: ${price.mid}")
    print(f"Change: ${price.change}")
    print(f"Change Percent: {price.change_percent}%")
    print(f"Status: {price.s}")
    print(f"Updated: {price.updated}")
    print("---")
```

**Get prices with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Symbol, Mid, Change_Price, Change_Percent, Date
prices = client.stocks.prices(
    "AAPL",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

for price in prices:
    print(f"Symbol: {price.Symbol}")
    print(f"Mid Price: ${price.Mid}")
    print(f"Change: ${price.Change_Price}")
    print(f"Change Percent: {price.Change_Percent}%")
    print(f"Date: {price.Date}")
    print("---")
```

## StockQuote Object

When using `OutputFormat.INTERNAL`, the `quotes()` method returns a list of `StockQuote` objects (or `StockQuotesHumanReadable` if `use_human_readable=True`) with the following properties:

### StockQuote Properties

- `symbol` (str): Stock symbol (e.g., "AAPL")
- `ask` (float): Ask price
- `askSize` (int): Ask size
- `bid` (float): Bid price
- `bidSize` (int): Bid size
- `mid` (float): Mid price
- `last` (float): Last trade price
- `change` (float): Price change
- `change_percent` (property): Alias for `changepct` - percentage change
- `changepct` (float): Percentage change (raw field name)
- `volume` (int): Trading volume
- `updated` (datetime.datetime): Last update timestamp

### StockQuotesHumanReadable Properties

When `use_human_readable=True`:
- `Symbol` (str): Stock symbol (e.g., "AAPL")
- `Ask` (float): Ask price
- `Ask_Size` (int): Ask size
- `Bid` (float): Bid price
- `Bid_Size` (int): Bid size
- `Mid` (float): Mid price
- `Last` (float): Last trade price
- `Change_Price` (float): Price change
- `Change_Percent` (float): Percentage change
- `Volume` (int): Trading volume
- `Date` (datetime.datetime): Last update timestamp

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
quotes = client.stocks.quotes("AAPL", output_format=OutputFormat.INTERNAL)
# or
quotes = client.stocks.quotes(symbols="AAPL", output_format=OutputFormat.INTERNAL)

for quote in quotes:
    print(f"Symbol: {quote.symbol}")
    print(f"Bid: ${quote.bid} (Size: {quote.bidSize})")
    print(f"Ask: ${quote.ask} (Size: {quote.askSize})")
    print(f"Mid: ${quote.mid}")
    print(f"Last: ${quote.last}")
    print(f"Change: ${quote.change} ({quote.change_percent}%)")
    print(f"Volume: {quote.volume}")
    print(f"Updated: {quote.updated}")
    print("---")
```

## StockCandle Object

When using `OutputFormat.INTERNAL`, the `candles()` method returns a list of `StockCandle` objects (or `StockCandlesHumanReadable` if `use_human_readable=True`) with the following properties:

### StockCandle Properties

- `t` (datetime.datetime): Timestamp of the candle
- `o` (float): Open price
- `h` (float): High price
- `l` (float): Low price
- `c` (float): Close price
- `v` (int): Volume

### StockCandlesHumanReadable Properties

When `use_human_readable=True`:
- `Date` (datetime.datetime): Timestamp of the candle
- `Open` (float): Open price
- `High` (float): High price
- `Low` (float): Low price
- `Close` (float): Close price
- `Volume` (int): Volume

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
candles = client.stocks.candles("AAPL", output_format=OutputFormat.INTERNAL)
# or
candles = client.stocks.candles(symbol="AAPL", output_format=OutputFormat.INTERNAL)

for candle in candles:
    print(f"Time: {candle.t}")
    print(f"Open: ${candle.o}")
    print(f"High: ${candle.h}")
    print(f"Low: ${candle.l}")
    print(f"Close: ${candle.c}")
    print(f"Volume: {candle.v}")
    print("---")
```

## StockEarnings Object

When using `OutputFormat.INTERNAL`, the `earnings()` method returns a `StockEarnings` object (or `StockEarningsHumanReadable` if `use_human_readable=True`). Unlike other methods that return lists, `earnings()` returns a single object containing lists of earnings data.

### StockEarnings Properties

- `s` (str): Status string
- `symbol` (list[str]): List of stock symbols
- `fiscalYear` (list[int]): List of fiscal years
- `fiscalQuarter` (list[int]): List of fiscal quarters
- `date` (list[datetime.datetime]): List of earnings dates
- `reportDate` (list[datetime.datetime]): List of report dates
- `reportTime` (list[str]): List of report times (e.g., "after close", "before open")
- `currency` (list[str]): List of currencies
- `reportedEPS` (list[float]): List of reported EPS values
- `estimatedEPS` (list[float]): List of estimated EPS values
- `surpriseEPS` (list[float]): List of surprise EPS values
- `surpriseEPSpct` (list[float]): List of surprise EPS percentages
- `updated` (list[datetime.datetime]): List of update timestamps

### StockEarningsHumanReadable Properties

When `use_human_readable=True`:
- `Symbol` (list[str]): List of stock symbols
- `Fiscal_Year` (list[int]): List of fiscal years
- `Fiscal_Quarter` (list[int]): List of fiscal quarters
- `Date` (list[datetime.datetime]): List of earnings dates
- `Report_Date` (list[datetime.datetime]): List of report dates
- `Report_Time` (list[str]): List of report times
- `Currency` (list[str]): List of currencies
- `Reported_EPS` (list[float]): List of reported EPS values
- `Estimated_EPS` (list[float]): List of estimated EPS values
- `Surprise_EPS` (list[float]): List of surprise EPS values
- `Surprise_EPS_Percent` (list[float]): List of surprise EPS percentages
- `Updated` (list[datetime.datetime]): List of update timestamps

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
earnings = client.stocks.earnings("AAPL", output_format=OutputFormat.INTERNAL)
# or
earnings = client.stocks.earnings(symbol="AAPL", output_format=OutputFormat.INTERNAL)

# Access status
print(f"Status: {earnings.s}")

# Access earnings data (all properties are lists)
for i in range(len(earnings.symbol)):
    print(f"Symbol: {earnings.symbol[i]}")
    print(f"Fiscal Year: {earnings.fiscalYear[i]}, Quarter: {earnings.fiscalQuarter[i]}")
    print(f"Date: {earnings.date[i]}")
    print(f"Report Date: {earnings.reportDate[i]}")
    print(f"Report Time: {earnings.reportTime[i]}")
    print(f"Reported EPS: {earnings.reportedEPS[i]}")
    print(f"Estimated EPS: {earnings.estimatedEPS[i]}")
    print(f"Surprise EPS: {earnings.surpriseEPS[i]}")
    print("---")
```

**Get earnings with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Symbol, Fiscal_Year, Fiscal_Quarter, Reported_EPS, Estimated_EPS, etc.
earnings = client.stocks.earnings(
    "AAPL",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

# Access earnings data (all properties are lists)
for i in range(len(earnings.Symbol)):
    print(f"Symbol: {earnings.Symbol[i]}")
    print(f"Fiscal Year: {earnings.Fiscal_Year[i]}, Quarter: {earnings.Fiscal_Quarter[i]}")
    print(f"Date: {earnings.Date[i]}")
    print(f"Report Date: {earnings.Report_Date[i]}")
    print(f"Report Time: {earnings.Report_Time[i]}")
    print(f"Reported EPS: {earnings.Reported_EPS[i]}")
    print(f"Estimated EPS: {earnings.Estimated_EPS[i]}")
    print(f"Surprise EPS: {earnings.Surprise_EPS[i]}")
    print("---")
```

## StockNews Object

When using `OutputFormat.INTERNAL`, the `news()` method returns a list of `StockNews` objects (or `StockNewsHumanReadable` if `use_human_readable=True`) with the following properties:

### StockNews Properties

- `symbol` (str): Stock symbol (e.g., "AAPL")
- `headline` (str): News headline
- `content` (str): News content/article text
- `source` (str): News source URL
- `publicationDate` (datetime.datetime): Publication date timestamp
- `updated` (datetime.datetime): Last update timestamp

### StockNewsHumanReadable Properties

When `use_human_readable=True`:
- `Symbol` (str): Stock symbol (e.g., "AAPL")
- `headline` (str): News headline
- `content` (str): News content/article text
- `source` (str): News source URL
- `publicationDate` (datetime.datetime): Publication date timestamp
- `Date` (datetime.datetime): Last update timestamp (replaces `updated`)

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
news = client.stocks.news("AAPL", output_format=OutputFormat.INTERNAL)
# or
news = client.stocks.news(symbol="AAPL", output_format=OutputFormat.INTERNAL)

for article in news:
    print(f"Symbol: {article.symbol}")
    print(f"Headline: {article.headline}")
    print(f"Source: {article.source}")
    print(f"Publication Date: {article.publicationDate}")
    print(f"Updated: {article.updated}")
    print(f"Content: {article.content[:200]}...")
    print("---")
```

**Get news with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Symbol, Date instead of symbol, updated
news = client.stocks.news(
    "AAPL",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

for article in news:
    print(f"Symbol: {article.Symbol}")
    print(f"Headline: {article.headline}")
    print(f"Source: {article.source}")
    print(f"Publication Date: {article.publicationDate}")
    print(f"Date: {article.Date}")
    print(f"Content: {article.content[:200]}...")
    print("---")
```

