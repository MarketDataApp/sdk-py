# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed (BREAKING)

- `BadStatusCodeError` and `RequestError`, replaced by the exception taxonomy below (#62). Migration: `except RequestError` becomes `except ServerError` (or `except (ServerError, NetworkError)`), `except BadStatusCodeError` becomes the specific class (`BadRequestError`, `AuthenticationError`, `ForbiddenError`, `NotFoundError`) or `MarketdataHttpError` to catch every HTTP failure. Error messages no longer carry the `Request failed with:` prefix.
- `MarketDataClientErrorResult` and the `@handle_exceptions` decorator. Resource methods now **raise** on failure instead of returning an error object (#20). Migration: replace `if isinstance(result, MarketDataClientErrorResult)` checks with `try` / `except BaseMarketdataException as e`; what used to be `result.error` is now the exception itself, and `result.support_info` is `e.support_info`. Errors that are not the SDK's own (Pydantic `ValidationError`, `FileExistsError`, `httpx` transport errors) propagate unwrapped.

### Added

- One exception class per failure, mapped from the HTTP status in a single place (SDK requirements §6.1 and §9.1): `BadRequestError` (400), `AuthenticationError` (401, never retried), `ForbiddenError` (403), `NotFoundError` (404 with an error message), `ServerError` (5xx), `NetworkError` (connection failures and timeouts, wrapped from `httpx` and retried), `ParseError` (undecodable body); `RateLimitError` now carries `retry_after` and the response on a 429 (#62)
- **404 `no_data` is no longer an error.** A valid question with an empty answer returns the empty value for the output format: a DataFrame with the model's columns and no rows, `[]` or `None` for `INTERNAL`, the `{"s": "no_data"}` body for `JSON`, a header-only file for `CSV`. In the fan-out calls a chunk or symbol with no data is left out of the merge (#62)

### Changed

- Retries follow SDK requirements §9.2: only server errors above 500 and network failures are retried; a plain 500, every 4xx and a 429 are final (#62)
- Every SDK exception now carries the full support context (`request_id`, `request_url`, `status_code`, `timestamp`, `message`, `exception_type`) and a `support_info` block; non-HTTP failures report `N/A` / `0` for the request fields (#20)
- All exception classes are re-exported from the package root (`from marketdata import BaseMarketdataException, ...`) (#20)
- `options.quotes()` raises `BadStatusCodeError` instead of returning an error object when none of the per-symbol responses is usable (#20)
- `stocks.quotes()` now requests `stocks/quotes/?symbols=...` instead of the deprecated `stocks/bulkquotes/`; the method, its parameters and its output are unchanged (#74)

### Added

- `client.utilities` resource with `status()`, `headers()` and `user()` for the `/status/`, `/headers/` and `/user/` endpoints, in every output format (#63)

### Fixed

- CSV files are created exclusively, so a path that appears between validation and the write fails the call instead of being silently overwritten; the `output/` directory is only created when a CSV is actually written, never on JSON/DataFrame/INTERNAL requests; CSV bytes are written verbatim on every platform (no doubled carriage returns on Windows) (#43)
- A caller-supplied `filename` for `OutputFormat.CSV` is now honored on every resource; it used to be validated and then replaced by a timestamped file in `output/` (#60)
- `stocks.candles()` no longer fetches every chunk-boundary day twice on intraday ranges longer than a year: the automatic year-sized chunks are now disjoint calendar-day ranges (#51)

### Security

- Caller-supplied symbols are now percent-encoded in request paths, preventing path traversal and query smuggling via untrusted input; valid symbols are unaffected
- `options.lookup()` neutralizes dot-segments in the lookup string so it cannot traverse to a different endpoint; valid lookup strings (including dates with slashes) are unaffected
- Token obfuscation in logs no longer reveals the token length, and never reveals any characters of short tokens
- API error messages extracted from response bodies are now bounded, so a malformed or hostile response cannot balloon exception messages and logs
- Malformed rate-limit headers no longer crash a successful request with a raw `KeyError`/`ValueError`; the SDK logs a warning and keeps the previous limits
- The PyPI publish action is pinned to a fixed release tag instead of a moving branch ref; the test workflow token is now read-only

## [1.3.0] - 2026-06-10

### Fixed

- `options.chain()` min/max bid/ask price filters are now actually validated (#32)
- `days_to_expiration` filter on `options.chain()` is now sent to the API correctly (was silently ignored) (#30)
- `options.expirations(columns=[...])` no longer returns an empty DataFrame (#23)
- `strike_limit` on `options.chain()` accepts integer values without API rejection (#24)
- `options.quotes()` now exposes `date`, `from`, and `to` params for historical date-range queries (#19)

### Added

- Package root re-exports — `from marketdata import MarketDataClient, MarketDataClientErrorResult, OutputFormat, DateFormat, Mode` (#17)
- `Retry-After` response header is now honored on retries
- API status check now uses the cached `/status` endpoint

### Changed

- Default logging level lowered to WARNING — SDK is quiet by default (#25)
- Retry backoff strategy updated

## [1.2.0] - 2026-02-13

### Fixed

- Timezone handling: API times are now correctly parsed; expirations use `dateformat=unix` for complete timestamps
- Token obfuscation in logs for security
- Stock candles now accept string input for 'from' and 'to' dates
- Settings model now allows extra environment variables without validation errors
- User agent string is now RFC 7231 compliant
- URL building for /user endpoint

### Added

- `support_info` and `support_context` properties on error results for enhanced debugging
- Improved exception wrapping ensures all errors include support context

### Changed

- Updated logging format and resource lifecycle logging
- Removed /user and /status requests from response logging
- User agent updated to match PyPI package name (marketdata-sdk-py)

## [1.1.0] - 2026-01-15

### Added

- **Enhanced date format handling for dataframe outputs**
  - Automatic detection of date/datetime columns from output schemas
  - Improved date format parameter support across all endpoints (stocks, options, funds, markets)
  - Better date handling for both pandas and polars handlers
  - Date format now properly respected when converting date/datetime columns in DataFrames

- **New example: Stock Prices Monitor**
  - Added `examples/stock_prices_monitor_example.py` - a terminal dashboard for monitoring stock prices
  - Features include:
    - Auto-refreshing terminal table with stock prices
    - Color-coded price changes (green for up, red for down)
    - Sortable by percentage change
    - Requires `rich` and `pandas` (optional dependencies)

### Changed

- Refactored dataframe output handlers to derive date/datetime columns from output schemas
- Improved date format conversion logic in both pandas and polars handlers
- Enhanced test coverage for date format handling across all resources

## [1.0.0] - 2025-01-XX

### Added

- Initial stable release of the Market Data Python SDK
- Support for stocks, options, funds, and markets resources
- Multiple output formats: DataFrame (pandas/polars), JSON, CSV, and internal Python objects
- Built-in retry logic with exponential backoff
- Rate limit tracking and management
- API status checking
- Comprehensive type safety with Pydantic validation
