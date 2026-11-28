# Utilities Resource

The `utilities` resource exposes four endpoints: the live status of every API service, an echo of the request headers as the API received them, the authenticated account's credit counters, and revoking the account's own API token.

## Accessing the Utilities Resource

```python
from marketdata import MarketDataClient

client = MarketDataClient()
utilities = client.utilities
```

All four methods include automatic retry logic. `status()`, `headers()` and `user()` never consume API credits, and `status()` and `headers()` work without a token (demo mode); `delete_token()` requires a token and goes through the same pre-flight credit check as every other `/v1/` endpoint. See the [README](../README.md) for general information about error handling, retry mechanisms, and output formats.

`status()`, `headers()` and `user()` live at the API root (`/status/`, `/headers/`, `/user/`), only speak JSON and accept no query parameters. The SDK therefore sends them bare and produces every output format client-side from the decoded JSON. `delete_token()` lives at the versioned `/v1/user/token/` and sends a bare `DELETE`, with the same JSON-only, client-side rendering. Of the universal parameters, only `output_format` and `filename` apply to any of the four.

## Columns a model does not declare

With `OutputFormat.INTERNAL`, a column the API sends before the SDK declares it does not fail the call: the result is built from the columns its model declares, and `marketdata.get_extra(row)` returns the others on each row of `status()`, named as the API sent them, with the row's own value. `user()` reads only its own keys and `headers()` keeps every key as a header, so neither keeps anything there. `delete_token()`'s only field is the status flag `s`, which every model in the SDK keeps out of `get_extra` and out of `DATAFRAME`/`CSV`, so there is nothing left for either of those two formats to carry. `JSON` and `DATAFRAME` carry it as a column, and `CSV` writes it in the file. See [Columns a model does not declare](../README.md#columns-a-model-does-not-declare) in the README for how long the values last and how they are decoded.

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

- `ServiceStatus` fields: `service` (str, e.g. `/v1/stocks/quotes/`), `status` (str, `online` or `offline`), `online` (bool), `uptimePct30d` (float, 0 to 1), `uptimePct90d` (float, 0 to 1), `updated` (datetime | None). The `is_online` property is true when both `online` and `status` say so.
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

Fetches the authenticated account's credit limit, remaining credits and options data permissions. Requires a token. The call is never blocked by the pre-flight rate-limit check and feeds that check with the balance the API reports, so it is the way to read the account's balance at any time.

#### Parameters

Same as `status()`: `output_format` and `filename`.

#### Returns

- `User`: `credit_limit` (int), `credits_remaining` (int, can be negative after an oversized request), `options_data_permissions` (str, empty when the plan has none) and the `has_options_data` property. The API body still names these fields `x-ratelimit-requests-*`; the SDK exposes them in API-credits terms.
- With `OutputFormat.JSON`, `OutputFormat.DATAFRAME` and `OutputFormat.CSV` the API's own field names are kept.
- Raises `AuthenticationError` without a valid token (`401`), and the usual taxonomy otherwise; see the [README](../README.md#error-handling).

#### Example

```python
user = client.utilities.user(output_format=OutputFormat.INTERNAL)
print(user)
# User: 99997/100000 credits remaining, options data: realtime
```

### `delete_token()`

Revokes the authenticated account's API token. Requires a token. The token used to make the call is unusable for any further request once it answers; a fresh one is needed to use the SDK again.

#### Parameters

Same as `status()`: `output_format` and `filename`.

#### Returns

- `TokenDeleted`: `s` (str), the API's success flag. It is the only field this envelope carries, so `DATAFRAME` and `CSV` (which keep `s` out like every other resource) have nothing left to show: a one-row, no-column DataFrame on pandas, an empty DataFrame on polars (which has no row with zero columns), and an empty CSV file.
- Raises `AuthenticationError` without a valid token (`401`), and the usual taxonomy otherwise; see the [README](../README.md#error-handling).

#### Example

```python
deleted = client.utilities.delete_token(output_format=OutputFormat.INTERNAL)
print(deleted)
# Token Deleted: ok
```
