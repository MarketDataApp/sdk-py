<div align="center">

# Market Data Python SDK v1.0
### Access Financial Data with Ease

> This is the official Python SDK for [Market Data](https://www.marketdata.app/). It provides developers with a powerful, easy-to-use interface to obtain real-time and historical financial data. Ideal for building financial applications, trading bots, and investment strategies.

[![Tests](https://github.com/MarketDataApp/sdk-py/actions/workflows/test.yml/badge.svg)](https://github.com/MarketDataApp/sdk-py/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/MarketDataApp/sdk-py/branch/main/graph/badge.svg)](https://codecov.io/gh/MarketDataApp/sdk-py)
[![License](https://img.shields.io/github/license/MarketDataApp/sdk-py.svg)](https://github.com/MarketDataApp/sdk-py/blob/main/LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/marketdata-sdk-py.svg)](https://pypi.org/project/marketdata-sdk-py/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)

#### Connect With The Market Data Community

[![Website](https://img.shields.io/badge/Website-marketdata.app-blue)](https://www.marketdata.app/)
[![Discord](https://img.shields.io/badge/Discord-join%20chat-7389D8.svg?logo=discord&logoColor=ffffff)](https://discord.com/invite/GmdeAVRtnT)
[![Twitter](https://img.shields.io/twitter/follow/MarketDataApp?style=social)](https://twitter.com/MarketDataApp)
[![Helpdesk](https://img.shields.io/badge/Support-Ticketing-ff69b4.svg?logo=TicketTailor&logoColor=white)](https://www.marketdata.app/dashboard/)

</div>

## Features

- **Real-time Stock Data**: Prices, quotes, candles (OHLCV), earnings, and news
- **Options Trading Data**: Complete options chains, expirations, strikes, quotes, and lookup
- **Mutual Funds**: Historical candles and pricing data
- **Market Status**: Real-time market open/closed status for multiple countries
- **Multiple Output Formats**: DataFrames (pandas/polars), JSON, CSV, or Python objects
- **Built-in Retry Logic**: Automatic retry with exponential backoff for reliable data fetching
- **Type-Safe**: Full Pydantic validation and type hints
- **Zero Config**: Works out of the box with sensible defaults

## Requirements

- Python >= 3.10

## Installation

### Basic Installation

Install from PyPI:

```bash
pip install marketdata-sdk-py
```

Or if you're using `uv`:

```bash
uv pip install marketdata-sdk-py
```

### Installation with DataFrame Support

To use `OutputFormat.DATAFRAME`, you need to install at least one DataFrame library. See [Optional Dependencies](#optional-dependencies) for details.

Install with pandas (recommended):
```bash
pip install "marketdata-sdk-py[pandas]"
# or using uv
uv pip install "marketdata-sdk-py[pandas]"
```

Install with polars:
```bash
pip install "marketdata-sdk-py[polars]"
# or using uv
uv pip install "marketdata-sdk-py[polars]"
```

Install with both:
```bash
pip install "marketdata-sdk-py[pandas,polars]"
# or using uv
uv pip install "marketdata-sdk-py[pandas,polars]"
```

### Local Development Installation

For local development, install from the project directory:

```bash
pip install .
# or with optional dependencies
pip install ".[pandas]"
```

## Configuration

The SDK requires a MarketData authentication token. You can provide it in two ways:

### Option 1: Environment variable (recommended)

Create a `.env` file in the project root:

```env
MARKETDATA_TOKEN=your_token_here
```

### Option 2: Pass token directly

You can pass the token when creating a client instance:

```python
from marketdata.client import MarketDataClient

client = MarketDataClient(token="your_token_here")
```

## Usage

### Create a client

```python
from marketdata.client import MarketDataClient
from logging import Logger

# Token will be automatically obtained from MARKETDATA_TOKEN environment variable
client = MarketDataClient()

# Or provide the token explicitly
client = MarketDataClient(token="your_token_here")

# You can also provide a custom logger
custom_logger = get_logger()  # Your custom logger setup
client = MarketDataClient(token="your_token_here", logger=custom_logger)
```

**Client Initialization Details:**

- The client automatically fetches rate limits by making a request to `/user/` endpoint during initialization
- The client includes a User-Agent header with the format `marketdata-py-{version}` (e.g., `marketdata-py-0.0.1`)
- The library version is automatically detected from the installed package
- All requests include an `Authorization: Bearer {token}` header
- The client uses `httpx.Client` for HTTP requests with automatic connection pooling

### Accessing Rate Limits

The client automatically fetches and tracks rate limits from the API. Rate limits are initialized when the client is created by making a request to `/user/` endpoint, and are updated after each API request based on response headers.

You can access current rate limits:

```python
client = MarketDataClient()

# Access current rate limits
rate_limits = client.rate_limits

# Access individual fields
print(f"Limit: {rate_limits.requests_limit}")
print(f"Remaining: {rate_limits.requests_remaining}")
print(f"Consumed: {rate_limits.requests_consumed}")
print(f"Reset at: {rate_limits.requests_reset}")

# Or use the formatted string representation
print(rate_limits)  # Shows: "Rate used X/Y, remaining: Z credits, next reset: ISO timestamp"
```

**Note:** Rate limits are tracked via the following response headers:
- `x-api-ratelimit-limit`: Total number of requests allowed
- `x-api-ratelimit-remaining`: Number of requests remaining
- `x-api-ratelimit-consumed`: Number of requests consumed
- `x-api-ratelimit-reset`: Unix timestamp when the rate limit resets

The `requests_reset` field is automatically converted to a `datetime.datetime` object for easier use.

### Resources

The SDK provides access to different market data resources:

- **Stocks**: Access stock prices, quotes, candles (OHLCV), earnings, and news
  - Methods: `prices()`, `quotes()`, `candles()`, `earnings()`, `news()`
  - See [Stocks Documentation](docs/stocks.md) for detailed usage

- **Options**: Access options chains, expiration data, strikes, quotes, and lookup
  - Methods: `chain()`, `expirations()`, `strikes()`, `quotes()`, `lookup()`
  - See [Options Documentation](docs/options.md) for detailed usage

- **Funds**: Access funds candles (OHLC) for mutual funds
  - Methods: `candles()`
  - See [Funds Documentation](docs/funds.md) for detailed usage

- **Markets**: Access market status information (open/closed) for dates and countries
  - Methods: `status()`
  - See [Markets Documentation](docs/markets.md) for detailed usage

> **Note:** For stocks, options, and funds resources, the `symbol`, `symbols`, or `lookup` parameter (depending on the method) can be passed as the first positional argument or as a keyword argument. All other parameters must be keyword-only. For markets resource, all parameters must be keyword-only.

#### Quick Example

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()

# Get stock prices (symbols can be passed positionally or as keyword)
df = client.stocks.prices("AAPL")
# or
df = client.stocks.prices(symbols="AAPL")
print(df)

# Get stock candles (symbol can be passed positionally or as keyword)
df = client.stocks.candles("AAPL")
# or
df = client.stocks.candles(symbol="AAPL")
print(df)

# Get options chain (symbol can be passed positionally or as keyword)
chain = client.options.chain("AAPL")
# or
chain = client.options.chain(symbol="AAPL")
print(chain)

# Get options strikes (symbol can be passed positionally or as keyword)
strikes = client.options.strikes("AAPL")
# or
strikes = client.options.strikes(symbol="AAPL")
print(strikes)

# Get options quotes (symbols can be passed positionally or as keyword)
# Note: quotes() takes option symbols (e.g., "AAPL240120C00150000"), not stock symbols
quotes = client.options.quotes("AAPL240120C00150000")
# or
quotes = client.options.quotes(symbols="AAPL240120C00150000")
print(quotes)

# Get options lookup (lookup can be passed positionally or as keyword)
# Format: "SYMBOL DD-MM-YYYY STRIKE SIDE" (e.g., "AAPL 20-12-2024 150.0 call")
lookup = client.options.lookup("AAPL 20-12-2024 150.0 call")
# or
lookup = client.options.lookup(lookup="AAPL 20-12-2024 150.0 call")
print(lookup)

# Get funds candles (symbol can be passed positionally or as keyword)
df = client.funds.candles("VFINX")
# or
df = client.funds.candles(symbol="VFINX")
print(df)

# Get market status (all parameters must be keyword-only)
df = client.markets.status(countback=7)
print(df)
```

## Output Formats

The SDK supports multiple output formats for API responses. See the [Universal Parameters](#universal-parameters) section for details on how to specify output formats.

- `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (default). Requires installing pandas or polars as an optional dependency. See [Optional Dependencies](#optional-dependencies) for installation instructions.
- `OutputFormat.INTERNAL`: Returns internal Python objects (see resource-specific documentation for details)
- `OutputFormat.JSON`: Returns raw JSON data (dictionary)
- `OutputFormat.CSV`: Writes CSV data to file and returns filename string

For detailed information about return types and object structures for each resource, see the specific resource documentation:
- [Stocks Documentation](docs/stocks.md) - Object types: `StockPrice`, `StockQuote`, `StockCandle`, `StockEarnings`, `StockNews`
- [Options Documentation](docs/options.md) - Object types: `OptionsExpirations`, `OptionsChain`, `OptionsStrikes`, `OptionsQuotes`, `OptionsLookup`
- [Funds Documentation](docs/funds.md) - Object type: `FundsCandle`
- [Markets Documentation](docs/markets.md) - Object type: `MarketStatus`

You can specify the output format when calling resource methods:

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()

# Get DataFrame (default) - symbols can be passed positionally or as keyword
df = client.stocks.prices("AAPL")
# or
df = client.stocks.prices(symbols="AAPL")

# Get internal objects
prices = client.stocks.prices("AAPL", output_format=OutputFormat.INTERNAL)
# or
prices = client.stocks.prices(symbols="AAPL", output_format=OutputFormat.INTERNAL)

# Get JSON
json_data = client.stocks.prices("AAPL", output_format=OutputFormat.JSON)
# or
json_data = client.stocks.prices(symbols="AAPL", output_format=OutputFormat.JSON)

# Get CSV
# All methods write to file and return filename string
csv_file = client.stocks.prices("AAPL", output_format=OutputFormat.CSV, filename="prices.csv")
# Get candles as internal objects
candles = client.stocks.candles("AAPL", output_format=OutputFormat.INTERNAL)
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.options.chain("AAPL", output_format=OutputFormat.CSV)
```

### CSV Output Behavior

When using `OutputFormat.CSV`, all resources write CSV data to a file and return the filename as a string. If `filename` is not provided, a timestamped file is automatically created in the `output/` directory (the directory is created if it doesn't exist).

**Note:** When specifying a custom `filename`, the directory must exist and the file must not already exist. See resource-specific documentation for details on CSV output format.

## Universal Parameters

All resource methods support universal parameters that can be used to customize the API request and response:

### `output_format` (OutputFormat, optional)
The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.

### `date_format` (DateFormat, optional)
The date format to use in the response. Defaults to `DateFormat.UNIX`. Available options:
- `DateFormat.TIMESTAMP`: ISO timestamp format
- `DateFormat.UNIX`: Unix timestamp (seconds since epoch)
- `DateFormat.SPREADSHEET`: Spreadsheet-compatible format

### `columns` (list[str], optional)
Specify which columns to include in the response. If not provided, all available columns are returned.

### `add_headers` (bool, optional)
Whether to include headers in the response. Uses API alias `headers`.

### `use_human_readable` (bool, optional)
Whether to use human-readable format for values. Uses API alias `human`.

### `mode` (Mode, optional)
The data feed mode to use. Available options:
- `Mode.LIVE`: Live market data
- `Mode.CACHED`: Cached data
- `Mode.DELAYED`: Delayed data

### `filename` (str | Path, optional)
File path for CSV output (only used with `output_format=OutputFormat.CSV`). 
- Must end with `.csv`
- Directory must exist (if filename is provided)
- File must not already exist
- If not provided, a timestamped file is created in `output/` directory (the directory is automatically created if it doesn't exist)

#### Example: Using Universal Parameters

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat, DateFormat, Mode
from pathlib import Path

client = MarketDataClient()

# Use custom date format and mode
df = client.stocks.prices(
    "AAPL",
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE
)

# Specify columns to include
df = client.stocks.prices(
    "AAPL",
    columns=["symbol", "mid", "change_percent"]
)

# Save CSV with custom filename
csv_file = client.stocks.prices(
    "AAPL",
    output_format=OutputFormat.CSV,
    filename=Path("data/aapl_prices.csv")
)
```

## Error Handling

The SDK uses a combination of exceptions and return values for error handling:

### `RateLimitError`

Raised when API rate limits are exceeded (before retry logic):

```python
from marketdata.client import MarketDataClient
from marketdata.exceptions import RateLimitError

try:
    client = MarketDataClient()
    df = client.stocks.prices("AAPL")
    # or
    df = client.stocks.prices(symbols="AAPL")
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
```

### `RequestError`

Raised for HTTP errors and retryable status codes. This exception is used internally by the retry mechanism. When a retryable status code (status code > 500 by default) is encountered, a `RequestError` is raised, which triggers the retry logic. After retries are exhausted or if the service is offline, the exception is caught by `@handle_exceptions` and converted to `MarketDataClientErrorResult`.

**Note:** This exception is typically caught internally by the `@handle_exceptions` decorator and converted to `MarketDataClientErrorResult`. You generally won't need to catch it directly unless you're working with the low-level `make_request` method.

### `ValueError`

Raised for various validation errors:

- Invalid date formats when parsing timestamps
- Invalid output format values
- Invalid filename format (must end with `.csv`, directory must exist, file must not exist)
- Invalid input parameters

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat
from pathlib import Path

try:
    client = MarketDataClient()
    # Invalid filename (doesn't end with .csv)
    csv_file = client.stocks.prices(
        "AAPL",
        output_format=OutputFormat.CSV,
        filename=Path("data/invalid.txt")
    )
except ValueError as e:
    print(f"Validation error: {e}")
```

### `MinMaxDateValidationError`

Raised when date range validation fails (e.g., `from_date` is greater than `to_date`). This exception is typically caught internally by the `@handle_exceptions` decorator and converted to `MarketDataClientErrorResult`. You generally won't need to catch it directly unless you're working with low-level validation.

```python
from marketdata.client import MarketDataClient
from marketdata.exceptions import MinMaxDateValidationError
from marketdata.sdk_error import MarketDataClientErrorResult
import datetime

try:
    client = MarketDataClient()
    # Invalid date range (from_date > to_date)
    result = client.stocks.candles(
        "AAPL",
        from_date=datetime.date(2024, 12, 31),
        to_date=datetime.date(2024, 1, 1)
    )
    if isinstance(result, MarketDataClientErrorResult):
        if isinstance(result.error, MinMaxDateValidationError):
            print(f"Date range validation error: {result.error}")
except MinMaxDateValidationError as e:
    print(f"Validation error: {e}")
```

### `KeywordOnlyArgumentError`

Raised when arguments are passed incorrectly. Only the `symbol` or `symbols` parameter can be passed as a positional argument. All other parameters must be keyword-only:

```python
from marketdata.client import MarketDataClient
from marketdata.exceptions import KeywordOnlyArgumentError
from marketdata.input_types.base import OutputFormat

try:
    client = MarketDataClient()
    # ❌ This will raise KeywordOnlyArgumentError
    df = client.stocks.prices("AAPL", OutputFormat.DATAFRAME)
    
    # ✅ Correct usage
    df = client.stocks.prices("AAPL", output_format=OutputFormat.DATAFRAME)
    # or
    df = client.stocks.prices(symbols="AAPL", output_format=OutputFormat.DATAFRAME)
except KeywordOnlyArgumentError as e:
    print(f"Invalid argument usage: {e}")
```

### `MarketDataClientErrorResult`

This is a special result type returned by resource methods when errors occur. It wraps the original exception and allows you to check for errors without exception handling. **All resource methods return either the expected result or `MarketDataClientErrorResult` - they never return `None`.**

```python
from marketdata.client import MarketDataClient
from marketdata.sdk_error import MarketDataClientErrorResult

client = MarketDataClient()
result = client.stocks.prices("AAPL")

# Check if the result is an error
if isinstance(result, MarketDataClientErrorResult):
    print(f"Error occurred: {result.error}")
    print(f"Error type: {type(result.error).__name__}")
else:
    print(result)
```

The `MarketDataClientErrorResult` object contains the original exception in its `error` attribute, which can be:
- `RateLimitError`: When rate limits are exceeded
- `MinMaxDateValidationError`: When date range validation fails (e.g., `from_date` > `to_date`)
- `ValueError`: When input validation fails (invalid formats, filenames, etc.)
- `RequestError`: When HTTP requests fail
- `BadStatusCodeError`: When HTTP requests return non-retryable error status codes
- Any other exception that occurs during request processing

## Retry Mechanism

The SDK includes automatic retry logic for handling transient errors. The retry mechanism is triggered when a `RequestError` exception occurs in methods decorated with `@api_error_handler`.

### Retry Configuration

- **Default retry attempts**: 3
- **Backoff strategy**: Exponential with multiplier 0.5, minimum wait 0.5 seconds, maximum wait 5 seconds
- **Retryable status codes**: The SDK retries on any HTTP status code greater than 500 (server errors). This includes common server error codes like 502 (Bad Gateway), 503 (Service Unavailable), 504 (Gateway Timeout), and others.
- **Default timeout**: 60 seconds per request

### How It Works

The retry mechanism only retries on `RequestError` exceptions and only if the API service status is `ONLINE` or `UNKNOWN`. When a retryable status code is encountered, a `RequestError` exception is raised internally, which triggers the retry logic. The retry adapter uses the `tenacity` library and will retry up to the specified number of attempts with exponential backoff between retries.

**Important:** Resource methods always return a value. They may return:
- The expected result (DataFrame, list of objects, dict, or str for CSV)
- `MarketDataClientErrorResult` if an error occurs (rate limits, validation errors, request failures, etc.)

Exceptions are caught internally by the `@handle_exceptions` decorator and converted to `MarketDataClientErrorResult`. However, some exceptions may still be raised before reaching the decorator (e.g., `RateLimitError` when rate limits cannot be checked).

Always check for `MarketDataClientErrorResult` return values and handle exceptions when calling resource methods:

```python
from marketdata.client import MarketDataClient
from marketdata.exceptions import RateLimitError, RequestError
from marketdata.sdk_error import MarketDataClientErrorResult

client = MarketDataClient()
try:
    result = client.stocks.prices("AAPL")
    # Check if the result is an error
    if isinstance(result, MarketDataClientErrorResult):
        print(f"Request failed: {result.error}")
        print(f"Error type: {type(result.error).__name__}")
    else:
        print(result)
except (RateLimitError, RequestError) as e:
    # These exceptions may be raised before reaching the decorator
    print(f"Request failed: {e}")
```

## API Status Checking

The SDK includes automatic API status checking for certain resource methods. When a `RequestError` occurs, the SDK verifies that the API service is online before retrying the request.

### How It Works

- **Automatic checking**: Methods with API status checking (`@api_error_handler` decorator) verify service availability when a `RequestError` occurs
- **Cached status**: API status information is cached and refreshed automatically every 4 minutes and 30 seconds
- **Service-specific**: Each method checks the status of its specific service endpoint
- **Retry logic**: The SDK only retries requests if the service status is `ONLINE` or `UNKNOWN`. If the service is `OFFLINE`, the error is raised immediately

### Methods with API Status Checking

All resource methods include API status checking and automatic retry logic. See the specific resource documentation for details on each method's behavior.

### Error Handling

If a service is offline when checked, the method raises the original `RequestError` exception instead of retrying:

```python
from marketdata.client import MarketDataClient
from marketdata.exceptions import RequestError

client = MarketDataClient()
try:
    result = client.stocks.candles("AAPL")
except RequestError as e:
    print(f"Service unavailable or request failed: {e}")
```

### Status Refresh Behavior

The SDK automatically refreshes the API status cache when:
- The cached status is older than 4 minutes and 30 seconds
- A `RequestError` occurs in a method with status checking

The status refresh request does not count against rate limits (`check_rate_limits=False`) and does not update rate limit tracking (`populate_rate_limits=False`), ensuring that status checking does not interfere with your API usage while providing up-to-date service availability information.

## Advanced Configuration

You can customize the base URL, API version, logging level, and universal parameters through environment variables:

```env
# Required
MARKETDATA_TOKEN=your_token_here

# API Configuration
MARKETDATA_BASE_URL=https://api.marketdata.app
MARKETDATA_API_VERSION=v1
MARKETDATA_LOGGING_LEVEL=INFO

# Universal Parameters (optional - can also be passed as method arguments)
MARKETDATA_OUTPUT_FORMAT=dataframe
MARKETDATA_DATE_FORMAT=unix
MARKETDATA_COLUMNS=symbol,mid,change_percent
MARKETDATA_ADD_HEADERS=true
MARKETDATA_USE_HUMAN_READABLE=false
MARKETDATA_MODE=live
```

**Defaults:**
- `MARKETDATA_BASE_URL`: `https://api.marketdata.app`
- `MARKETDATA_API_VERSION`: `v1`
- `MARKETDATA_LOGGING_LEVEL`: `INFO`
- Universal parameters: `None` (uses method defaults)

**Note:** Universal parameters set via environment variables will be used as defaults for all API calls, but can be overridden by passing them as method arguments. See the [Universal Parameters](#universal-parameters) section for available values.

## Project Structure

```
.
├── docs/
│   ├── stocks.md         # Stocks resource documentation
│   ├── options.md        # Options resource documentation
│   ├── funds.md          # Funds resource documentation
│   └── markets.md        # Markets resource documentation
├── src/
│   ├── tests/            # Test suite
│   │   ├── conftest.py   # Pytest configuration and fixtures
│   │   ├── test_client.py
│   │   ├── test_stocks_prices.py
│   │   ├── test_stocks_candles.py
│   │   ├── test_options_chain.py
│   │   ├── test_options_expirations.py
│   │   ├── test_options_quotes.py
│   │   ├── test_params.py
│   │   └── data/         # Test data fixtures
│   └── marketdata/
│       ├── __init__.py
│       ├── client.py          # Main MarketDataClient class
│       ├── exceptions.py      # Custom exceptions (RateLimitError, RequestError, KeywordOnlyArgumentError)
│       ├── logger.py          # Logging configuration
│       ├── params.py          # Parameter decorators and validation (@universal_params)
│       ├── retry.py           # Retry mechanism using tenacity
│       ├── settings.py        # Configuration and environment variables
│       ├── types.py           # Data types (UserRateLimits)
│       ├── utils.py           # Utility functions (format_timestamp, initialize_dataframe, etc.)
│       ├── docs.py            # Documentation generation utilities
│       ├── internal_settings.py  # Internal settings (MAX_CONCURRENT_REQUESTS)
│       ├── input_types/       # Input validation types
│       │   ├── __init__.py
│       │   ├── base.py        # Base input type classes (OutputFormat, DateFormat, Mode, UserUniversalAPIParams)
│       │   ├── stocks.py      # Stocks input types (StocksPricesInput, StocksQuotesInput, StocksCandlesInput)
│       │   ├── funds.py       # Funds input types (FundsCandlesInput)
│       │   ├── markets.py     # Markets input types (MarketStatusInput)
│       │   └── options.py     # Options input types (OptionsChainInput, OptionsExpirationsInput, OptionsStrikesInput, OptionsQuotesInput, OptionsLookupInput)
│       ├── output_types/      # Output data types
│       │   ├── __init__.py
│       │   ├── stocks_prices.py  # Stock prices output types (StockPrice, StockPricesHumanReadable)
│       │   ├── stocks_quotes.py  # Stock quotes output types (StockQuote, StockQuotesHumanReadable)
│       │   ├── stocks_candles.py  # Stock candles output types (StockCandle, StockCandlesHumanReadable)
│       │   ├── stocks_earnings.py  # Stock earnings output types (StockEarnings, StockEarningsHumanReadable)
│       │   ├── stocks_news.py  # Stock news output types (StockNews, StockNewsHumanReadable)
│       │   ├── funds_candles.py   # Funds candles output types (FundsCandle, FundsCandlesHumanReadable)
│       │   ├── markets_status.py  # Markets status output types (MarketStatus, MarketStatusHumanReadable)
│       │   ├── options_chain.py   # Options chain output types (OptionsChain)
│       │   ├── options_expirations.py  # Options expirations output types (OptionsExpirations)
│       │   ├── options_quotes.py  # Options quotes output types (OptionsQuotes)
│       │   ├── options_strikes.py  # Options strikes output types (OptionsStrikes)
│       │   └── options_lookup.py  # Options lookup output types (OptionsLookup)
│       └── resources/
│           ├── __init__.py
│           ├── base.py        # BaseResource class with common functionality
│           ├── stocks/        # Stocks API resource
│           │   ├── __init__.py  # StocksResource class definition
│           │   ├── prices.py  # Stock prices endpoint
│           │   ├── quotes.py  # Stock quotes endpoint
│           │   ├── candles.py # Stock candles endpoint
│           │   ├── earnings.py # Stock earnings endpoint
│           │   └── news.py    # Stock news endpoint
│           ├── funds/         # Funds API resource
│           │   ├── __init__.py  # FundsResource class definition
│           │   └── candles.py # Funds candles endpoint
│           ├── markets/       # Markets API resource
│           │   ├── __init__.py  # MarketsResource class definition
│           │   └── status.py  # Markets status endpoint
│           └── options/       # Options API resource
│               ├── __init__.py  # OptionsResource class definition
│               ├── chain.py   # Options chain endpoint
│               ├── expirations.py  # Options expirations endpoint
│               ├── strikes.py  # Options strikes endpoint
│               ├── quotes.py  # Options quotes endpoint
│               └── lookup.py  # Options lookup endpoint
└── pyproject.toml        # Project configuration and dependencies
```

## Dependencies

### Required

- `httpx>=0.28.1`: HTTP client library for making API requests
- `pydantic>=2.12.5`: Data validation and settings management
- `pydantic-settings>=2.12.0`: Configuration management from environment variables
- `tenacity>=9.1.2`: Retry logic library for handling transient errors

### Optional Dependencies

The SDK supports multiple DataFrame libraries for `OutputFormat.DATAFRAME`. You must install at least one of the following:

- **pandas** (recommended): `pandas>=2.3.3`
- **polars**: `polars-lts-cpu>=1.33.1`

#### Installation

Install with pandas (recommended):
```bash
pip install "marketdata-sdk-py[pandas]"
# or using uv
uv pip install "marketdata-sdk-py[pandas]"
```

Install with polars:
```bash
pip install "marketdata-sdk-py[polars]"
# or using uv
uv pip install "marketdata-sdk-py[polars]"
```

Install with both:
```bash
pip install "marketdata-sdk-py[pandas,polars]"
# or using uv
uv pip install "marketdata-sdk-py[pandas,polars]"
```

#### DataFrame Handler Priority

When using `OutputFormat.DATAFRAME`, the SDK automatically selects an available DataFrame library in the following order:
1. **pandas** (if installed)
2. **polars** (if pandas is not installed)

If neither pandas nor polars is installed, a `ValueError` will be raised when attempting to use `OutputFormat.DATAFRAME`:
```python
ValueError: No dataframe output handler found
```

**Note:** You can use other output formats (`OutputFormat.INTERNAL`, `OutputFormat.JSON`, `OutputFormat.CSV`) without installing pandas or polars.

### Development Dependencies

- `black>=25.11.0`: Code formatter
- `isort>=7.0.0`: Import sorter
- `pandas>=2.3.3`: DataFrame library (for testing)
- `polars-lts-cpu>=1.33.1`: DataFrame library (for testing)
- `pytest>=9.0.1`: Testing framework
- `respx>=0.22.0`: HTTPX mocking library for tests

## Implementation Details

### Date Format Handling

The SDK automatically handles multiple date formats:

- **ISO timestamp strings**: Parsed using `datetime.fromisoformat()`
- **Unix timestamps**: Parsed using `datetime.fromtimestamp()` (seconds since epoch)
- **Spreadsheet dates**: Values between 0 and 60000 are treated as Excel-style dates (days since 1899-12-30)

All timestamps in response objects are automatically converted to `datetime.datetime` objects when using `OutputFormat.INTERNAL`. When using `OutputFormat.DATAFRAME`, timestamp conversion behavior varies by resource. See the specific resource documentation for details.

### DataFrame Processing

When using `OutputFormat.DATAFRAME`, the SDK performs automatic data cleaning:

- The `s` (status) column is removed from all DataFrames
- DataFrames are automatically indexed by their primary identifier (see resource-specific documentation for details)
- Timestamp columns are converted to `datetime.datetime` objects in most cases (see resource-specific documentation for exceptions)

For detailed information about DataFrame structure and indexing for each method, see the specific resource documentation.

### Parameter Validation

The SDK uses Pydantic for input validation:

- All input parameters are validated using Pydantic models
- Boolean parameters are converted to lowercase strings for the API (`"true"`/`"false"`)
- List parameters are joined with commas
- Enum parameters use their `.value` attribute
- Date parameters are formatted appropriately for the API

### Concurrent Requests

The SDK uses concurrent requests for efficient data fetching in specific scenarios:

- **`stocks.candles()`**: For intraday resolutions (minutely/hourly), large date ranges are automatically split into year-long chunks and fetched concurrently (up to 50 concurrent requests by default)
- **`options.quotes()`**: Multiple option symbols are fetched concurrently (up to 50 concurrent requests by default)

When concurrent requests are used, responses are automatically merged into a single result. If no valid responses are received, a `MarketDataClientErrorResult` is returned.

See the specific resource documentation for details on concurrent request behavior.

### Rate Limit Tracking

Rate limits are tracked via response headers and updated after each request:

- Rate limit information is extracted from response headers after every API call
- The `UserRateLimits` object is updated automatically
- Rate limit checking happens before each request (unless `check_rate_limits=False`)
- If rate limits are exhausted, a `RateLimitError` is raised before making the request

## Development

### Linting

```bash
./lint.sh
```

### Build

```bash
./build.sh
```

## License

See the [LICENSE](LICENSE) file for more details.
