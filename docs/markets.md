# Markets Resource

The `markets` resource provides access to market status information, allowing you to check whether markets are open or closed for specific dates, countries, or date ranges.

## Accessing the Markets Resource

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
markets = client.markets
```

All methods in the markets resource include API status checking and automatic retry logic. See the [README](../README.md) for general information about error handling, retry mechanisms, and output formats.

## Methods

### `status()`

Fetches market status information (open/closed) for one or more dates. Supports filtering by country and various date range options. This method includes API status checking and automatic retry logic.

> **Note:** All parameters must be keyword-only.

#### Parameters

- `country` (str, optional): The country to fetch the market status for (e.g., "US", "UK")
- `date` (datetime.date, optional): A specific date to fetch the market status for
- `from_date` (datetime.date, optional): The start date to fetch market status for
- `to_date` (datetime.date, optional): The end date to fetch market status for. When both `from_date` and `to_date` are provided, the date range is validated (from_date must be before to_date)
- `countback` (int, optional): The number of days to fetch market status for (alternative to date range)
- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame (requires pandas or polars to be installed)
  - `OutputFormat.INTERNAL`: Returns a list of `MarketStatus` or `MarketStatusHumanReadable` objects
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

- If `output_format=OutputFormat.DATAFRAME`: A pandas or polars DataFrame with market status data (indexed by date). The DataFrame is automatically processed:
  - The `s` column (status) is removed from the DataFrame
  - The DataFrame is indexed by the `date` column (or `Date` if human-readable)
  - All timestamp fields are automatically converted to `datetime.datetime` objects
- If `output_format=OutputFormat.INTERNAL`: A list of `MarketStatus` objects (or `MarketStatusHumanReadable` if `use_human_readable=True`)
- If `output_format=OutputFormat.JSON`: A dictionary with raw JSON data from the API
- If `output_format=OutputFormat.CSV`: A string containing the filename where CSV data was written
- `MarketDataClientErrorResult`: If an error occurs (rate limits, validation errors, request failures, etc.)

> **Note:** Always check for `MarketDataClientErrorResult` return values. The method never returns `None`.

#### Date Range Validation

When both `from_date` and `to_date` are provided, the method validates that `from_date` is before `to_date`. If this validation fails, a `ValueError` is raised.

#### Examples

**Get current market status (DataFrame):**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
df = client.markets.status()
print(df)
```

**Get market status for a specific date:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
df = client.markets.status(date=datetime.date(2024, 12, 25))
print(df)
```

**Get market status for a date range:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
df = client.markets.status(
    from_date=datetime.date(2024, 12, 1),
    to_date=datetime.date(2024, 12, 31)
)
print(df)
```

**Get market status using countback:**

```python
from marketdata.client import MarketDataClient

client = MarketDataClient()
# Get market status for the last 30 days
df = client.markets.status(countback=30)
print(df)
```

**Get market status for a specific country:**

```python
import datetime
from marketdata.client import MarketDataClient

client = MarketDataClient()
df = client.markets.status(
    country="US",
    date=datetime.date(2024, 12, 25)
)
print(df)
```

**Get market status as internal objects:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
status_list = client.markets.status(
    output_format=OutputFormat.INTERNAL,
    countback=7
)

for status in status_list:
    print(f"Date: {status.date}")
    print(f"Status: {status.status}")
    print("---")
```

**Get market status with human-readable format:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# Uses Status and Date instead of status and date
status_list = client.markets.status(
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True,
    countback=7
)

for status in status_list:
    print(f"Date: {status.Date}")
    print(f"Status: {status.Status}")
    print("---")
```

**Get market status as JSON:**

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
json_data = client.markets.status(
    output_format=OutputFormat.JSON,
    countback=7
)
print(json_data)
```

**Get market status as CSV:**

```python
from pathlib import Path
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
# CSV is written to file and filename is returned
# If filename is not provided, a timestamped file is created in output/ directory
csv_file = client.markets.status(
    output_format=OutputFormat.CSV,
    countback=30
)
# or with custom filename (directory must exist and file must not exist)
csv_file = client.markets.status(
    output_format=OutputFormat.CSV,
    countback=30,
    filename=Path("data/market_status.csv")
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
df = client.markets.status(
    from_date=datetime.date(2024, 12, 1),
    to_date=datetime.date(2024, 12, 31),
    date_format=DateFormat.TIMESTAMP,
    mode=Mode.LIVE,
    columns=["date", "status"]
)
```

## MarketStatus Object

When using `OutputFormat.INTERNAL`, the `status()` method returns a list of `MarketStatus` objects with the following properties:

### Properties

- `date` (datetime.datetime): The date for which the market status applies
- `status` (str): Market status, typically "open" or "closed"

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
status_list = client.markets.status(
    output_format=OutputFormat.INTERNAL,
    countback=7
)

for status in status_list:
    print(f"Date: {status.date}")
    print(f"Status: {status.status}")
    print(f"Formatted: {status}")  # Uses __str__ method
    print("---")
```

## MarketStatusHumanReadable Object

When using `OutputFormat.INTERNAL` with `use_human_readable=True`, the `status()` method returns a list of `MarketStatusHumanReadable` objects with the following properties:

### Properties

- `Date` (datetime.datetime): The date for which the market status applies
- `Status` (str): Market status, typically "open" or "closed"

### Example Usage

```python
from marketdata.client import MarketDataClient
from marketdata.input_types.base import OutputFormat

client = MarketDataClient()
status_list = client.markets.status(
    output_format=OutputFormat.INTERNAL,
    use_human_readable=True,
    countback=7
)

for status in status_list:
    print(f"Date: {status.Date}")
    print(f"Status: {status.Status}")
    print(f"Formatted: {status}")  # Uses __str__ method
    print("---")
```

