# Utilities Resource

The `utilities` resource exposes the three service endpoints of the API: the live status of every API service, an echo of the request headers as the API received them, and the authenticated account's credit counters.

## Accessing the Utilities Resource

```python
from marketdata import MarketDataClient

client = MarketDataClient()
utilities = client.utilities
```

All three methods include automatic retry logic. They never consume API credits, and `status()` and `headers()` work without a token (demo mode). See the [README](../README.md) for general information about error handling, retry mechanisms, and output formats.

These endpoints live at the API root (`/status/`, `/headers/`, `/user/`), only speak JSON and accept no query parameters. The SDK therefore sends them bare and produces every output format client-side from the decoded JSON. Of the universal parameters, only `output_format` and `filename` apply.

## Methods

### `status()`

Fetches the live status of every API service: whether it is online, its 30 and 90 day uptime and when the status was last updated.

> **Note:** All parameters must be keyword-only.

#### Parameters

- `output_format` (OutputFormat, optional): The format of the returned data. Defaults to `OutputFormat.DATAFRAME`.
  - `OutputFormat.DATAFRAME`: Returns a pandas or polars DataFrame with one row per service (indexed by `service` in pandas)
  - `OutputFormat.INTERNAL`: Returns a list of `ServiceStatus` objects
  - `OutputFormat.JSON`: Returns the decoded JSON as a dictionary
  - `OutputFormat.CSV`: Writes a CSV file with one row per service and returns the filename
- `filename` (str | Path, optional): File path for CSV output (only used with `output_format=OutputFormat.CSV`). Must end with `.csv`, the directory must exist and the file must not already exist. If not provided, a timestamped file is created in the `output/` directory.

#### Returns

- `ServiceStatus` fields: `service` (str, e.g. `/v1/stocks/quotes/`), `status` (str, `online` or `offline`), `online` (bool), `uptimePct30d` (float, 0 to 1), `uptimePct90d` (float, 0 to 1), `updated` (datetime). The `is_online` property is true when both `online` and `status` say so.
- Raises a `BaseMarketdataException` subclass if an error occurs; see the [README](../README.md#error-handling).

#### Example

```python
from marketdata import MarketDataClient, OutputFormat

client = MarketDataClient()

for service in client.utilities.status(output_format=OutputFormat.INTERNAL):
    print(service)
# Service Status: /v1/markets/status/ online (30d: 100.00%, 90d: 99.49%), Updated: 2026-09-03 11:13:14-04:00
# ...
```

### `headers()`

Echoes the request headers as the API received them, including the IP the API detected. Useful to debug proxies and IP allow-lists. The API masks the token in the `authorization` value before echoing it back.

#### Parameters

Same as `status()`: `output_format` and `filename`.

#### Returns

- `RequestHeaders`: `headers` (dict, names normalized to lowercase) plus the helpers `get(name)` (case-insensitive), `detected_ip` (from `cf-connecting-ip`, falling back to `x-real-ip`), `user_agent` and `authorization`.
- With `OutputFormat.DATAFRAME` a one-row DataFrame with one column per header; with `OutputFormat.CSV` a two-line file.
- Raises a `BaseMarketdataException` subclass if an error occurs; see the [README](../README.md#error-handling).

#### Example

```python
headers = client.utilities.headers(output_format=OutputFormat.INTERNAL)
print(headers.detected_ip)   # the IP an allow-list on your account must contain
print(headers.user_agent)    # marketdata-sdk-py/1.3.0
```

### `user()`

Fetches the authenticated account's credit limit, remaining credits and options data permissions. Requires a token. The call is never blocked by the pre-flight rate-limit check and refreshes the client's rate-limit state from the response headers, so it is the way to recover an up-to-date balance.

#### Parameters

Same as `status()`: `output_format` and `filename`.

#### Returns

- `User`: `credit_limit` (int), `credits_remaining` (int, can be negative after an oversized request), `options_data_permissions` (str, empty when the plan has none) and the `has_options_data` property. The API body still names these fields `x-ratelimit-requests-*`; the SDK exposes them in API-credits terms.
- With `OutputFormat.JSON`, `OutputFormat.DATAFRAME` and `OutputFormat.CSV` the API's own field names are kept.
- Raises `BadStatusCodeError` on failure, including `401` without a valid token; see the [README](../README.md#error-handling).

#### Example

```python
user = client.utilities.user(output_format=OutputFormat.INTERNAL)
print(user)
# User: 99997/100000 credits remaining, options data: realtime
```
