# Options Resource

The `options` resource provides access to options market data, including expiration dates, strike prices, option chains, and quotes with various filtering capabilities.

## Accessing the Options Resource

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
options = client.options
```

All methods in the options resource include API status checking and automatic retry logic. See the [README](../README.md) for general information about error handling, retry mechanisms, and output formats.

## Methods

### `expirations()`

Fetches available expiration dates for a given symbol. This method includes API status checking and automatic retry logic.

> **Note:** The `symbol` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbol` (str): Stock symbol (e.g., "AAPL")
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns an `OptionsExpirations` object
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string
- `strike` (float, optional): Filter by strike price
- `date` (datetime.date, optional): Filter by specific date

**Universal Parameters** (available for all options methods):

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

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with expiration dates (indexed by expirations). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `expirations` column if present
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: An `OptionsExpirations` object (or `OptionsExpirationsHumanReadable` if `use_human_readable=True`) (single object, not a list)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get all expirations for a symbol:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.options.expirations("AAPL")
# or
df = client.options.expirations(symbol="AAPL")
print(df)
```

**Get expirations as internal object:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
expirations = client.options.expirations("AAPL", output_format=OutputFormat.INTERNAL)
# or
expirations = client.options.expirations(symbol="AAPL", output_format=OutputFormat.INTERNAL)

if expirations:
    print(f"Status: {expirations.s}")
    print(f"Expirations: {expirations.expirations}")
    print(f"Updated: {expirations.updated}")
```

Note: `expirations()` returns a single `OptionsExpirations` object, not a list. The `expirations` property contains a list of expiration dates.

**Get expirations as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
json_data = client.options.expirations("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.options.expirations(symbol="AAPL", output_format=OutputFormat.JSON)
print(json_data)
```

**Get expirations as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.options.expirations("AAPL", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.options.expirations(
    "AAPL",
    output_format=OutputFormat.CSV,
    filename=Path("data/expirations.csv")
)
# or
csv_file = client.options.expirations(
    symbol="AAPL",
    output_format=OutputFormat.CSV,
    filename=Path("data/expirations.csv")
)

if csv_file:
    print(f"CSV saved to: {csv_file}")
```

**Filter by strike and date:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.options.expirations(
    "AAPL",
    strike=150.0,
    date=datetime.date(2024, 12, 31)
)
# or
df = client.options.expirations(
    symbol="AAPL",
    strike=150.0,
    date=datetime.date(2024, 12, 31)
)
print(df)
```

### `chain()`

Fetches the options chain for a given symbol with extensive filtering options. This method includes API status checking and automatic retry logic.

> **Note:** The `symbol` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbol` (str): Stock symbol (e.g., "AAPL")
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns an `OptionsChain` object
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string

**Universal Parameters** (available for all options methods):

- `date_format` (DateFormat, optional): The date format to use. Defaults to `DateFormat.UNIX`.
  - `DateFormat.TIMESTAMP`: ISO timestamp format
  - `DateFormat.UNIX`: Unix timestamp (seconds since epoch)
  - `DateFormat.SPREADSHEET`: Spreadsheet-compatible format
- `columns` (list[str], optional): List of column names to include in the response
- `add_headers` (bool, optional): Whether to add headers to the response
- `use_human_readable` (bool, optional): Whether to use human-readable format
- `mode` (Mode, optional): The data feed mode to use (`Mode.LIVE`, `Mode.CACHED`, `Mode.DELAYED`)
- `filename` (str | Path, optional): File path for CSV output (only used with `output_format=OutputFormat.CSV`). Must end with `.csv`, directory must exist, and file must not already exist. If not provided, a timestamped file is created in `output/` directory (the directory is automatically created if it doesn't exist).

**Expiration Filters:**

- `date` (datetime.date, optional): Filter by specific expiration date
- `expiration` (datetime.date, optional): Filter by expiration date
- `days_to_expiration` (int, optional): Filter by days until expiration
- `from_date` (datetime.date, optional): Filter expirations from this date
- `to_date` (datetime.date, optional): Filter expirations to this date
- `month` (int, optional): Filter by expiration month (1-12)
- `year` (int, optional): Filter by expiration year
- `weekly` (bool, optional): Filter for weekly expirations
- `monthly` (bool, optional): Filter for monthly expirations
- `quarterly` (bool, optional): Filter for quarterly expirations

**Strike Filters:**

- `strike` (str, optional): Filter by strike price (e.g., "150", "ATM", "ITM", "OTM")
- `delta` (float, optional): Filter by delta value
- `strike_limit` (float, optional): Limit the number of strikes
- `range` (str, optional): Strike range filter

**Price / Liquidity Filters:**

- `min_bid` (float, optional): Minimum bid price
- `max_bid` (float, optional): Maximum bid price
- `min_ask` (float, optional): Minimum ask price
- `max_ask` (float, optional): Maximum ask price
- `max_bid_ask_spread` (float, optional): Maximum bid-ask spread
- `max_bid_ask_spread_pct` (float, optional): Maximum bid-ask spread percentage
- `min_open_interest` (int, optional): Minimum open interest
- `min_volume` (int, optional): Minimum volume

**Other Filters:**

- `nonstandard` (bool, optional): Include non-standard options
- `side` (str, optional): Filter by side ("call" or "put")
- `am` (bool, optional): Filter for AM expirations
- `pm` (bool, optional): Filter for PM expirations

#### Returns

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with the options chain data (indexed by optionSymbol). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `optionSymbol` column if present
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: An `OptionsChain` object (or `OptionsChainHumanReadable` if `use_human_readable=True`) (single object, not a list)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get full options chain:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
chain = client.options.chain("AAPL")
# or
chain = client.options.chain(symbol="AAPL")
print(chain)
```

**Filter by expiration date:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
chain = client.options.chain(
    "AAPL",
    expiration=datetime.date(2024, 12, 20)
)
# or
chain = client.options.chain(
    symbol="AAPL",
    expiration=datetime.date(2024, 12, 20)
)
print(chain)
```

**Filter by strike and side:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
chain = client.options.chain(
    "AAPL",
    strike="ATM",
    side="call"
)
# or
chain = client.options.chain(
    symbol="AAPL",
    strike="ATM",
    side="call"
)
print(chain)
```

**Filter by liquidity:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
chain = client.options.chain(
    "AAPL",
    min_open_interest=100,
    min_volume=50,
    max_bid_ask_spread_pct=5.0
)
# or
chain = client.options.chain(
    symbol="AAPL",
    min_open_interest=100,
    min_volume=50,
    max_bid_ask_spread_pct=5.0
)
print(chain)
```

**Complex filtering example:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
chain = client.options.chain(
    "AAPL",
    expiration=datetime.date(2024, 12, 20),
    strike="ITM",
    side="call",
    min_open_interest=100,
    min_volume=50
)
# or
chain = client.options.chain(
    symbol="AAPL",
    expiration=datetime.date(2024, 12, 20),
    strike="ITM",
    side="call",
    min_open_interest=100,
    min_volume=50
)
print(chain)
```

**Get chain as internal object:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
chain = client.options.chain("AAPL", output_format=OutputFormat.INTERNAL)
# or
chain = client.options.chain(symbol="AAPL", output_format=OutputFormat.INTERNAL)

if chain:
    print(f"Status: {chain.s}")
    print(f"Number of options: {len(chain.optionSymbol)}")
    print(f"Underlying symbols: {set(chain.underlying)}")
```

Note: `chain()` returns a single `OptionsChain` object, not a list. All properties of `OptionsChain` are lists where each index represents a single option contract.

**Get chain as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
json_data = client.options.chain("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.options.chain(symbol="AAPL", output_format=OutputFormat.JSON)
print(json_data)
```

**Get chain as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.options.chain("AAPL", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.options.chain(
    "AAPL",
    output_format=OutputFormat.CSV,
    filename=Path("data/chain.csv")
)
# or
csv_file = client.options.chain(
    symbol="AAPL",
    output_format=OutputFormat.CSV,
    filename=Path("data/chain.csv")
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
chain = client.options.chain(
    "AAPL",
    expiration=datetime.date(2024, 12, 20),
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["optionSymbol", "strike", "bid", "ask"]
)
```

### `lookup()`

Fetches the option symbol for a given lookup string. The lookup string should contain the underlying symbol, expiration date, strike price, and option side formatted as a single string (e.g., "AAPL 28-00-2023 200.0 call"). This method includes API status checking and automatic retry logic.

> **Note:** The `lookup` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `lookup` (str): The lookup string containing the underlying symbol, expiration date (formatted as "DD-MM-YYYY"), strike price, and option side (e.g., "AAPL 28-00-2023 200.0 call" or "AAPL 20-12-2024 150.0 put")
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns an `OptionsLookup` or `OptionsLookupHumanReadable` object
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string

**Universal Parameters** (available for all options methods):

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

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with the option symbol (indexed by optionSymbol or Symbol). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `optionSymbol` column if present (or `Symbol` if human-readable)
- If `output_format=OutputFormat.INTERNAL`: An `OptionsLookup` object (or `OptionsLookupHumanReadable` if `use_human_readable=True`) (single object, not a list)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get option symbol for specific parameters:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# lookup can be passed positionally or as keyword argument
# Format: "SYMBOL DD-MM-YYYY STRIKE SIDE" (e.g., "AAPL 20-12-2024 150.0 call")
lookup_result = client.options.lookup("AAPL 20-12-2024 150.0 call")
# or
lookup_result = client.options.lookup(lookup="AAPL 20-12-2024 150.0 call")
print(lookup_result)
```

**Get lookup as internal object:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# lookup can be passed positionally or as keyword argument
lookup = client.options.lookup(
    "AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.INTERNAL
)
# or
lookup = client.options.lookup(
    lookup="AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.INTERNAL
)

if lookup:
    print(f"Option Symbol: {lookup.optionSymbol}")
    print(f"Status: {lookup.s}")
```

Note: `lookup()` returns a single `OptionsLookup` object, not a list.

**Get lookup as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# lookup can be passed positionally or as keyword argument
json_data = client.options.lookup(
    "AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.JSON
)
# or
json_data = client.options.lookup(
    lookup="AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.JSON
)
print(json_data)
```

**Get lookup as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# lookup can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.options.lookup(
    "AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.CSV
)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.options.lookup(
    "AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.CSV,
    filename=Path("data/lookup.csv")
)
# or
csv_file = client.options.lookup(
    lookup="AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.CSV,
    filename=Path("data/lookup.csv")
)

if csv_file:
    print(f"CSV saved to: {csv_file}")
```

### `quotes()`

Fetches options quotes for one or more option symbols. This method includes API status checking, automatic retry logic, and supports concurrent requests for multiple symbols (up to 50 concurrent requests by default).

> **Note:** The `symbols` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbols` (str | list[str]): A single option symbol string (e.g., "AAPL240120C00150000") or a list of option symbols
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns an `OptionsQuotes` object
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string

**Universal Parameters** (available for all options methods):

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

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with options quotes data (indexed by optionSymbol/Symbol). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `optionSymbol` column if present (or `Symbol` if human-readable)
  - All timestamp fields are automatically converted to `datetime.datetime` objects
  - Data from multiple symbols is merged into a single DataFrame
- If `output_format=OutputFormat.INTERNAL`: An `OptionsQuotes` object (or `OptionsQuotesHumanReadable` if `use_human_readable=True`) (single object, not a list) containing merged data from all requested symbols. All properties are lists where each index represents a single option contract.
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API (merged from all requested symbols)
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written (merged from all requested symbols)
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, no valid responses received, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`. The method uses concurrent requests (up to 50 concurrent requests by default) to fetch quotes for multiple symbols efficiently.

#### Examples

**Get quotes for a single option symbol:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
quotes = client.options.quotes("AAPL240120C00150000")
# or
quotes = client.options.quotes(symbols="AAPL240120C00150000")
print(quotes)
```

**Get quotes for multiple option symbols:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
quotes = client.options.quotes([
    "AAPL240120C00150000",
    "AAPL240120P00150000",
    "AAPL240120C00160000"
])
# or
quotes = client.options.quotes(symbols=[
    "AAPL240120C00150000",
    "AAPL240120P00150000",
    "AAPL240120C00160000"
])
print(quotes)
```

**Get quotes as internal object:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
quotes = client.options.quotes("AAPL240120C00150000", output_format=OutputFormat.INTERNAL)
# or
quotes = client.options.quotes(symbols="AAPL240120C00150000", output_format=OutputFormat.INTERNAL)

if quotes:
    print(f"Status: {quotes.s}")
    print(f"Number of options: {len(quotes.optionSymbol)}")
```

Note: `quotes()` returns a single `OptionsQuotes` object, not a list. All properties of `OptionsQuotes` are lists where each index represents a single option contract. When multiple symbols are requested, the data is merged into a single object.

**Get quotes as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
json_data = client.options.quotes("AAPL240120C00150000", output_format=OutputFormat.JSON)
# or
json_data = client.options.quotes(symbols="AAPL240120C00150000", output_format=OutputFormat.JSON)
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
csv_file = client.options.quotes("AAPL240120C00150000", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.options.quotes(
    "AAPL240120C00150000",
    output_format=OutputFormat.CSV,
    filename=Path("data/quotes.csv")
)
# or
csv_file = client.options.quotes(
    symbols="AAPL240120C00150000",
    output_format=OutputFormat.CSV,
    filename=Path("data/quotes.csv")
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
quotes = client.options.quotes(
    ["AAPL240120C00150000", "AAPL240120P00150000"],
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["optionSymbol", "strike", "bid", "ask", "volume"]
)
```

### `strikes()`

Fetches available strike prices for a given symbol. This method includes API status checking and automatic retry logic. It can filter strikes by expiration date or specific date.

> **Note:** The `symbol` parameter can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only.

#### Parameters

- `symbol` (str): Stock symbol (e.g., "AAPL")
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns an `OptionsStrikes` object
  - `OutputFormat.JSON`: Returns raw JSON data
  - `OutputFormat.CSV`: Writes CSV to file and returns filename string
- `expiration` (datetime.date, optional): Filter by expiration date
- `date` (datetime.date, optional): Filter by specific date

**Universal Parameters** (available for all options methods):

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

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with strike prices. The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - Strike prices are returned as columns where each column name corresponds to an expiration date (e.g., "2025-12-12", "2025-12-19")
  - The `updated` column contains the Unix timestamp (not converted to datetime in DataFrame format)
  - Each expiration date column contains a list of strike prices (floats) for that expiration
- If `output_format=OutputFormat.INTERNAL`: An `OptionsStrikes` object (or `OptionsStrikesHumanReadable` if `use_human_readable=True`) (single object, not a list)
  - The `updated` field (or `Date` if human-readable) is automatically converted to a `datetime.datetime` object
  - Dynamic fields correspond to expiration dates, each containing a list of strike prices (floats)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Examples

**Get all strikes for a symbol:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.options.strikes("AAPL")
# or
df = client.options.strikes(symbol="AAPL")
print(df)
```

**Filter strikes by expiration date:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.options.strikes(
    "AAPL",
    expiration=datetime.date(2024, 12, 20)
)
# or
df = client.options.strikes(
    symbol="AAPL",
    expiration=datetime.date(2024, 12, 20)
)
print(df)
# DataFrame structure: columns are expiration dates (e.g., "2024-12-20"), 
# plus an "updated" column with Unix timestamp
```

**Filter strikes by date:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
df = client.options.strikes(
    "AAPL",
    date=datetime.date(2024, 12, 20)
)
# or
df = client.options.strikes(
    symbol="AAPL",
    date=datetime.date(2024, 12, 20)
)
print(df)
# DataFrame structure: columns are expiration dates, plus an "updated" column
```

**Get strikes as internal object:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
strikes = client.options.strikes("AAPL", output_format=OutputFormat.INTERNAL)
# or
strikes = client.options.strikes(symbol="AAPL", output_format=OutputFormat.INTERNAL)

if strikes:
    print(f"Status: {strikes.s}")
    print(f"Updated: {strikes.updated}")
    # Access strike prices by expiration date (dynamic fields)
    # Strike fields are named by expiration date (e.g., "2024-12-20")
    for key, value in strikes.__dict__.items():
        if key not in ["s", "updated"]:
            print(f"{key}: {len(value)} strikes")
```

Note: `strikes()` returns a single `OptionsStrikes` object, not a list. The `OptionsStrikes` object contains strike prices as dynamic fields where each field name corresponds to an expiration date, and the field value is a list of strike prices (floats).

**Get strikes as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
json_data = client.options.strikes("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.options.strikes(symbol="AAPL", output_format=OutputFormat.JSON)
print(json_data)
```

**Get strikes as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.options.strikes("AAPL", output_format=OutputFormat.CSV)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.options.strikes(
    "AAPL",
    output_format=OutputFormat.CSV,
    filename=Path("data/strikes.csv")
)
# or
csv_file = client.options.strikes(
    symbol="AAPL",
    output_format=OutputFormat.CSV,
    filename=Path("data/strikes.csv")
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
strikes = client.options.strikes(
    "AAPL",
    expiration=datetime.date(2024, 12, 20),
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE
)
```

**Understanding the DataFrame structure:**

The strikes DataFrame has a unique structure where:
- Each column (except `updated`) represents an expiration date (e.g., "2025-12-12", "2025-12-19")
- Each expiration date column contains a list of strike prices (floats) for that expiration
- The `updated` column contains a Unix timestamp (seconds since epoch)
- Different expiration dates may have different numbers of strikes, so columns may have different lengths

```python
df = client.options.strikes("AAPL")
print(df.columns)  # Shows: Index(['updated', '2025-12-12', '2025-12-19', ...], dtype='object')
print(df['2025-12-12'].dropna().tolist())  # List of strikes for Dec 12, 2025
print(df['updated'].iloc[0])  # Unix timestamp
```

## OptionsExpirations Object

When using `OutputFormat.INTERNAL` with `expirations()`, the method returns an `OptionsExpirations` object (or `OptionsExpirationsHumanReadable` if `use_human_readable=True`) with the following properties:

### OptionsExpirations Properties

- `s` (str): Status string
- `expirations` (list[datetime.datetime]): List of expiration dates
- `updated` (datetime.datetime): Last update timestamp

### OptionsExpirationsHumanReadable Properties

When `use_human_readable=True`:
- `Expirations` (list[datetime.datetime]): List of expiration dates
- `Date` (datetime.datetime): Last update timestamp (replaces `updated`)

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
expirations = client.options.expirations("AAPL", output_format=OutputFormat.INTERNAL)
# or
expirations = client.options.expirations(symbol="AAPL", output_format=OutputFormat.INTERNAL)

if expirations:
    print(f"Status: {expirations.s}")
    for exp_date in expirations.expirations:
        print(f"Expiration: {exp_date.strftime('%Y-%m-%d')}")
    print(f"Updated: {expirations.updated}")
```

## OptionsChain Object

When using `OutputFormat.INTERNAL` with `chain()`, the method returns an `OptionsChain` object (or `OptionsChainHumanReadable` if `use_human_readable=True`) with the following properties:

### OptionsChain Properties

All properties are lists with the same length, where each index represents a single option contract:

- `s` (str): Status string
- `optionSymbol` (list[str]): List of option symbols
- `underlying` (list[str]): List of underlying stock symbols
- `expiration` (list[datetime.datetime]): List of expiration dates
- `side` (list[str]): List of option sides ("call" or "put")
- `strike` (list[float]): List of strike prices
- `firstTraded` (list[datetime.datetime]): List of first traded dates
- `dte` (list[int]): List of days to expiration
- `updated` (list[datetime.datetime]): List of last update timestamps
- `bid` (list[float]): List of bid prices
- `bidSize` (list[int]): List of bid sizes
- `mid` (list[float]): List of mid prices
- `ask` (list[float]): List of ask prices
- `askSize` (list[int]): List of ask sizes
- `last` (list[float]): List of last trade prices
- `openInterest` (list[int]): List of open interest values
- `volume` (list[int]): List of volume values
- `inTheMoney` (list[bool]): List indicating if options are in the money
- `intrinsicValue` (list[float]): List of intrinsic values
- `extrinsicValue` (list[float]): List of extrinsic values
- `underlyingPrice` (list[float]): List of underlying prices
- `iv` (list[float]): List of implied volatilities
- `delta` (list[float]): List of delta values
- `gamma` (list[float]): List of gamma values
- `theta` (list[float]): List of theta values
- `vega` (list[float]): List of vega values

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
chain = client.options.chain("AAPL", output_format=OutputFormat.INTERNAL)
# or
chain = client.options.chain(symbol="AAPL", output_format=OutputFormat.INTERNAL)

if chain:
    print(f"Status: {chain.s}")
    print(f"Total options: {len(chain.optionSymbol)}")

    # Access individual option data by index
    for i in range(min(5, len(chain.optionSymbol))):
        print(f"\nOption {i+1}:")
        print(f"  Symbol: {chain.optionSymbol[i]}")
        print(f"  Strike: ${chain.strike[i]}")
        print(f"  Side: {chain.side[i]}")
        print(f"  Expiration: {chain.expiration[i].strftime('%Y-%m-%d')}")
        print(f"  Bid: ${chain.bid[i]}")
        print(f"  Ask: ${chain.ask[i]}")
        print(f"  Mid: ${chain.mid[i]}")
        print(f"  Volume: {chain.volume[i]}")
        print(f"  Open Interest: {chain.openInterest[i]}")
        print(f"  Delta: {chain.delta[i]}")
        print(f"  IV: {chain.iv[i]}")
```

### OptionsChainHumanReadable Properties

When `use_human_readable=True`, the object uses human-readable field names similar to `OptionsQuotesHumanReadable`:
- `Symbol` (list[str]): List of option symbols (replaces `optionSymbol`)
- `Underlying` (list[str]): List of underlying stock symbols
- `Expiration_Date` (list[datetime.datetime]): List of expiration dates (replaces `expiration`)
- `Option_Side` (list[str]): List of option sides (replaces `side`)
- `Strike` (list[float | int]): List of strike prices
- `First_Traded` (list[datetime.datetime]): List of first traded dates (replaces `firstTraded`)
- `Days_To_Expiration` (list[int]): List of days to expiration (replaces `dte`)
- `Date` (list[datetime.datetime]): List of last update timestamps (replaces `updated`)
- `Bid`, `Bid_Size`, `Mid`, `Ask`, `Ask_Size`, `Last`, `Open_Interest`, `Volume`, `In_The_Money`, `Intrinsic_Value`, `Extrinsic_Value`, `Underlying_Price`, `IV`, `Delta`, `Gamma`, `Theta`, `Vega`: Same structure as `OptionsQuotesHumanReadable`
```

## OptionsQuotes Object

When using `OutputFormat.INTERNAL` with `quotes()`, the method returns an `OptionsQuotes` object (or `OptionsQuotesHumanReadable` if `use_human_readable=True`) with the following properties:

### OptionsQuotes Properties

All properties are lists with the same length, where each index represents a single option contract:

- `s` (str): Status string
- `optionSymbol` (list[str]): List of option symbols
- `underlying` (list[str]): List of underlying stock symbols
- `expiration` (list[datetime.datetime]): List of expiration dates
- `side` (list[str]): List of option sides ("call" or "put")
- `strike` (list[float]): List of strike prices
- `firstTraded` (list[datetime.datetime]): List of first traded dates
- `dte` (list[int]): List of days to expiration
- `updated` (list[datetime.datetime]): List of last update timestamps
- `bid` (list[float]): List of bid prices
- `bidSize` (list[int]): List of bid sizes
- `mid` (list[float]): List of mid prices
- `ask` (list[float]): List of ask prices
- `askSize` (list[int]): List of ask sizes
- `last` (list[float]): List of last trade prices
- `openInterest` (list[int]): List of open interest values
- `volume` (list[int]): List of volume values
- `inTheMoney` (list[bool]): List indicating if options are in the money
- `intrinsicValue` (list[float]): List of intrinsic values
- `extrinsicValue` (list[float]): List of extrinsic values
- `underlyingPrice` (list[float]): List of underlying prices
- `iv` (list[float]): List of implied volatilities
- `delta` (list[float]): List of delta values
- `gamma` (list[float]): List of gamma values
- `theta` (list[float]): List of theta values
- `vega` (list[float]): List of vega values

### OptionsQuotesHumanReadable Properties

When `use_human_readable=True`:
- `Symbol` (list[str]): List of option symbols (replaces `optionSymbol`)
- `Underlying` (list[str]): List of underlying stock symbols
- `Expiration_Date` (list[datetime.datetime]): List of expiration dates (replaces `expiration`)
- `Option_Side` (list[str]): List of option sides (replaces `side`)
- `Strike` (list[float | int]): List of strike prices
- `First_Traded` (list[datetime.datetime]): List of first traded dates (replaces `firstTraded`)
- `Days_To_Expiration` (list[int]): List of days to expiration (replaces `dte`)
- `Date` (list[datetime.datetime]): List of last update timestamps (replaces `updated`)
- `Bid` (list[float]): List of bid prices
- `Bid_Size` (list[int]): List of bid sizes (replaces `bidSize`)
- `Mid` (list[float]): List of mid prices
- `Ask` (list[float]): List of ask prices
- `Ask_Size` (list[int]): List of ask sizes (replaces `askSize`)
- `Last` (list[float]): List of last trade prices
- `Open_Interest` (list[int]): List of open interest values (replaces `openInterest`)
- `Volume` (list[int]): List of volume values
- `In_The_Money` (list[bool]): List indicating if options are in the money (replaces `inTheMoney`)
- `Intrinsic_Value` (list[float]): List of intrinsic values (replaces `intrinsicValue`)
- `Extrinsic_Value` (list[float]): List of extrinsic values (replaces `extrinsicValue`)
- `Underlying_Price` (list[float]): List of underlying prices (replaces `underlyingPrice`)
- `IV` (list[float]): List of implied volatilities (replaces `iv`)
- `Delta` (list[float]): List of delta values
- `Gamma` (list[float]): List of gamma values
- `Theta` (list[float]): List of theta values
- `Vega` (list[float]): List of vega values

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbols can be passed positionally or as keyword argument
quotes = client.options.quotes("AAPL240120C00150000", output_format=OutputFormat.INTERNAL)
# or
quotes = client.options.quotes(symbols="AAPL240120C00150000", output_format=OutputFormat.INTERNAL)

if quotes:
    print(f"Status: {quotes.s}")
    print(f"Total options: {len(quotes.optionSymbol)}")

    # Access individual option data by index
    for i in range(min(5, len(quotes.optionSymbol))):
        print(f"\nOption {i+1}:")
        print(f"  Symbol: {quotes.optionSymbol[i]}")
        print(f"  Strike: ${quotes.strike[i]}")
        print(f"  Side: {quotes.side[i]}")
        print(f"  Expiration: {quotes.expiration[i].strftime('%Y-%m-%d')}")
        print(f"  Bid: ${quotes.bid[i]}")
        print(f"  Ask: ${quotes.ask[i]}")
        print(f"  Mid: ${quotes.mid[i]}")
        print(f"  Volume: {quotes.volume[i]}")
        print(f"  Open Interest: {quotes.openInterest[i]}")
        print(f"  Delta: {quotes.delta[i]}")
        print(f"  IV: {quotes.iv[i]}")
```

**Get quotes with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
quotes = client.options.quotes(
    "AAPL240120C00150000",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

if quotes:
    print(f"Total options: {len(quotes.Symbol)}")
    for i in range(min(5, len(quotes.Symbol))):
        print(f"\nOption {i+1}:")
        print(f"  Symbol: {quotes.Symbol[i]}")
        print(f"  Strike: ${quotes.Strike[i]}")
        print(f"  Option Side: {quotes.Option_Side[i]}")
        print(f"  Expiration Date: {quotes.Expiration_Date[i].strftime('%Y-%m-%d')}")
        print(f"  Bid: ${quotes.Bid[i]}")
        print(f"  Ask: ${quotes.Ask[i]}")
        print(f"  Mid: ${quotes.Mid[i]}")
        print(f"  Volume: {quotes.Volume[i]}")
        print(f"  Open Interest: {quotes.Open_Interest[i]}")
        print(f"  Delta: {quotes.Delta[i]}")
        print(f"  IV: {quotes.IV[i]}")
```

**Note:** When requesting quotes for multiple symbols, the `OptionsQuotes` object merges all data into a single object. All properties remain lists where each index corresponds to a single option contract from any of the requested symbols.

## OptionsStrikes Object

When using `OutputFormat.INTERNAL` with `strikes()`, the method returns an `OptionsStrikes` object (or `OptionsStrikesHumanReadable` if `use_human_readable=True`) with the following properties:

### OptionsStrikes Properties

- `s` (str): Status string
- `updated` (datetime.datetime): Last update timestamp
- Dynamic strike fields: The object contains additional fields where each field name corresponds to an expiration date (e.g., "2024-12-20"), and the field value is a list of strike prices (list[float])

### OptionsStrikesHumanReadable Properties

When `use_human_readable=True`:
- `Date` (datetime.datetime): Last update timestamp (replaces `updated`)
- Dynamic strike fields: Same structure as `OptionsStrikes`, where field names correspond to expiration dates and values are lists of strike prices

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# symbol can be passed positionally or as keyword argument
strikes = client.options.strikes("AAPL", output_format=OutputFormat.INTERNAL)
# or
strikes = client.options.strikes(symbol="AAPL", output_format=OutputFormat.INTERNAL)

if strikes:
    print(f"Status: {strikes.s}")
    print(f"Updated: {strikes.updated}")
    
    # Access strike prices by expiration date
    # The field names are dynamic and correspond to expiration dates
    for key, value in strikes.__dict__.items():
        if key not in ["s", "updated"]:
            print(f"\nExpiration {key}:")
            print(f"  Number of strikes: {len(value)}")
            print(f"  Strikes: {value[:5]}...")  # Show first 5 strikes
```

**Note:** The `OptionsStrikes` object uses dynamic fields to store strike prices. Each expiration date becomes a field name, and the value is a list of strike prices (floats) for that expiration. This allows flexible access to strikes organized by expiration date.

## OptionsLookup Object

When using `OutputFormat.INTERNAL` with `lookup()`, the method returns an `OptionsLookup` object (or `OptionsLookupHumanReadable` if `use_human_readable=True`) with the following properties:

### Properties

- `s` (str): Status string
- `optionSymbol` (str): The option symbol string

### OptionsLookupHumanReadable Properties

When `use_human_readable=True`:
- `Symbol` (str): The option symbol string

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# lookup can be passed positionally or as keyword argument
lookup = client.options.lookup(
    "AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.INTERNAL
)
# or
lookup = client.options.lookup(
    lookup="AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.INTERNAL
)

if lookup:
    print(f"Status: {lookup.s}")
    print(f"Option Symbol: {lookup.optionSymbol}")
```

**Get lookup with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Symbol instead of optionSymbol
lookup = client.options.lookup(
    "AAPL 20-12-2024 150.0 call",
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True
)

if lookup:
    print(f"Option Symbol: {lookup.Symbol}")
```

