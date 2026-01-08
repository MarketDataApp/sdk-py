# Funds Resource

The `funds` resource provides access to funds market data, including historical candles (OHLC data) for mutual funds.

## Accessing the Funds Resource

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
funds = client.funds
```

All methods in the funds resource include API status checking and automatic retry logic. See the [README](../README.md) for general information about error handling, retry mechanisms, and output formats.

## Methods

### `candles()`

Fetches funds candles (OHLC data) for a symbol with support for various timeframes and date ranges. Unlike stocks candles, this method does not automatically split large date ranges into concurrent requests. This method includes API status checking and automatic retry logic.

> **Note:** The `symbol` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbol` (str): A single fund symbol (e.g., "VFINX")
- `resolution` (str, optional): The timeframe resolution for candles. Defaults to `"D"` (daily). Valid formats:
  - Numeric with unit: `"1"`, `"1D"`, `"1W"`, `"1M"`, `"1Y"`
  - Unit only: `"D"`, `"W"`, `"M"`, `"Y"`
  - Descriptive: `"daily"`, `"weekly"`, `"monthly"`, `"yearly"`
  - **Note:** Funds candles do not support minutely (`M`) or hourly (`H`) resolutions
- `from_date` (datetime.date, optional): The start date to fetch candles for
- `to_date` (datetime.date, optional): The end date to fetch candles for
- `countback` (int, optional): The number of candles to fetch (alternative to date range)
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns a list of `FundsCandle` or `FundsCandlesHumanReadable` objects
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string
- `date_format` (DateFormat, optional): The date format to use. Defaults to `DateFormat.UNIX`.
  - `DateFormat.TIMESTAMP`: ISO timestamp format
  - `DateFormat.UNIX`: Unix timestamp (seconds since epoch)
  - `DateFormat.SPREADSHEET`: Spreadsheet-compatible format
- `columns` (list[str], optional): List of column names to include in the response
- `add_headers` (bool, optional): Whether to add headers to the response
- `use_human_readable` (bool, optional): Whether to use human-readable format (uses `Date`, `Open`, `High`, `Low`, `Close` instead of `t`, `o`, `h`, `l`, `c`)
- `mode` (Mode, optional): The data feed mode to use (`Mode.LIVE`, `Mode.CACHED`, `Mode.DELAYED`)
- `filename` (str | Path, optional): File path for CSV output (only used with `output_format=OutputFormat.CSV`). Must end with `.csv`, directory must exist, and file must not already exist. If not provided, a timestamped file is created in `output/` directory (the directory is automatically created if it doesn't exist).

#### Returns

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with candle data (indexed by timestamp/Date). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `t` column (timestamp) or `Date` column (if human-readable)
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: A list of `FundsCandle` objects (or `FundsCandlesHumanReadable` if `use_human_readable=True`)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get daily candles for a fund symbol (DataFrame):**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.funds.candles("VFINX")
# or
df = client.funds.candles(symbol="VFINX")
print(df)
```

**Get candles with specific resolution:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get weekly candles
df = client.funds.candles("VFINX", resolution="W")
# Get monthly candles
df = client.funds.candles("VFINX", resolution="M")
# Get yearly candles
df = client.funds.candles("VFINX", resolution="Y")
```

**Get candles for a date range:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Fetch candles for a specific date range
# Note: Unlike stocks candles, funds candles do not automatically split large date ranges into concurrent requests
df = client.funds.candles(
    "VFINX",
    resolution="D",
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31)
)
print(df)
```

**Get candles using countback:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get last 100 daily candles
df = client.funds.candles("VFINX", resolution="D", countback=100)
print(df)
```

**Get candles as internal objects:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
candles = client.funds.candles("VFINX", output_format=OutputFormat.INTERNAL)
# or
candles = client.funds.candles(symbol="VFINX", output_format=OutputFormat.INTERNAL)

for candle in candles:
    print(f"Time: {candle.t}")
    print(f"Open: {candle.o}, High: {candle.h}, Low: {candle.l}, Close: {candle.c}")
```

**Get candles with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Date, Open, High, Low, Close instead of t, o, h, l, c
candles = client.funds.candles(
    "VFINX",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

for candle in candles:
    print(f"Date: {candle.Date}")
    print(f"Open: {candle.Open}, High: {candle.High}, Low: {candle.Low}, Close: {candle.Close}")
```

**Get candles as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
json_data = client.funds.candles("VFINX", output_format=OutputFormat.JSON)
# or
json_data = client.funds.candles(symbol="VFINX", output_format=OutputFormat.JSON)
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
csv_file = client.funds.candles("VFINX", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.funds.candles(
    "VFINX", 
    resolution="D",
    output_format=OutputFormat.CSV,
    filename=Path("data/VFINX_candles.csv")
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
df = client.funds.candles(
    "VFINX",
    resolution="D",
    from_date=datetime.date(2023, 1, 1),
    to_date=datetime.date(2023, 12, 31),
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["t", "o", "h", "l", "c"]
)
```

## FundsCandle Object

When using `OutputFormat.INTERNAL`, the `candles()` method returns a list of `FundsCandle` objects (or `FundsCandlesHumanReadable` if `use_human_readable=True`) with the following properties:

### FundsCandle Properties

- `t` (datetime.datetime): Timestamp of the candle
- `o` (float): Open price
- `h` (float): High price
- `l` (float): Low price
- `c` (float): Close price

**Note:** Unlike stock candles, funds candles do not include volume data.

### FundsCandlesHumanReadable Properties

When `use_human_readable=True`:
- `Date` (datetime.datetime): Timestamp of the candle
- `Open` (float): Open price
- `High` (float): High price
- `Low` (float): Low price
- `Close` (float): Close price

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
candles = client.funds.candles("VFINX", output_format=OutputFormat.INTERNAL)
# or
candles = client.funds.candles(symbol="VFINX", output_format=OutputFormat.INTERNAL)

for candle in candles:
    print(f"Time: {candle.t}")
    print(f"Open: ${candle.o}")
    print(f"High: ${candle.h}")
    print(f"Low: ${candle.l}")
    print(f"Close: ${candle.c}")
    print("---")
```

