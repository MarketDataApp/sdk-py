# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed (BREAKING)

- `BadStatusCodeError` and `RequestError`, replaced by the exception taxonomy below (#62). Migration: `except RequestError` becomes `except ServerError` (or `except (ServerError, NetworkError)`), `except BadStatusCodeError` becomes the specific class (`BadRequestError`, `AuthenticationError`, `ForbiddenError`, `NotFoundError`, `InternalError`) or `MarketdataHttpError` to catch every HTTP failure. Error messages no longer carry the `Request failed with:` prefix.
- `MarketDataClientErrorResult` and the `@handle_exceptions` decorator. Resource methods now **raise** on failure instead of returning an error object (#20). Migration: replace `if isinstance(result, MarketDataClientErrorResult)` checks with `try` / `except BaseMarketdataException as e`; what used to be `result.error` is now the exception itself, and `result.support_info` is `e.support_info`. Errors that are not the SDK's own (Pydantic `ValidationError`, `FileExistsError`, `httpx` transport errors) propagate unwrapped.
- `client.rate_limits`. The client-level snapshot was last-response-wins under concurrent calls, so `credits_consumed` read from it could belong to any request (#49). Migration: read `marketdata.get_meta(result).rate_limits` on the result of the call you care about, or call `client.utilities.user()` for the account balance.
- `OptionsQuotes.get_null_dict()`, `OptionsQuotes.get_null_csv_string()` and their `OptionsQuotesHumanReadable` twins. They existed only to fabricate an empty row for a symbol whose body could not be decoded, which #82 replaced with a `ParseError`; nothing in the SDK calls them. Migration: an empty answer is already rendered by the resource itself (a header-only CSV, an empty DataFrame, `[]` / `None`).

### Changed

- **BREAKING**: every request now times out after 99 seconds, with a 2 second connect timeout, instead of one 60 second bound shared by connect, read, write and pool (SDK requirements §10). The value is fixed and not configurable, and `MarketDataClient._make_request` no longer takes a `timeout` argument: a call that should give up sooner is cancelled by the caller rather than given a shorter bound, so an SDK request cannot outlive the API's own limit. A connect or read timeout is still a `NetworkError` and is still retried (#64)
- Retries follow SDK requirements §9.2: only `ServerError` (501 and above) and `NetworkError` are retried; `InternalError` (500), every 4xx, a 429 and a `NetworkError` the client itself caused (a base URL without a scheme, a malformed request, a proxy that refuses the connection) are final (#62)
- Every SDK exception now carries the full support context (`request_id`, `request_url`, `status_code`, `timestamp`, `message`, `exception_type`) and a `support_info` block; non-HTTP failures report `N/A` / `0` for the request fields (#20)
- All exception classes are re-exported from the package root (`from marketdata import BaseMarketdataException, ...`) (#20)
- `options.quotes()` raises `MarketdataHttpError` instead of returning an error object when none of the per-symbol responses is usable (#20)
- `stocks.quotes()` now requests `stocks/quotes/?symbols=...` instead of the deprecated `stocks/bulkquotes/`; the method, its parameters and its output are unchanged (#74)
- **BREAKING**: `UserRateLimits` speaks in API credits, as the product does (SDK requirements §8.1): `requests_limit` → `credit_limit`, `requests_remaining` → `credits_remaining`, `requests_consumed` → `credits_consumed`, `requests_reset` → `reset_time`. The old names are gone, with no aliases; its string form now reads `Credits used X/Y, remaining: Z, reset at: <ISO timestamp>` (#48)
- The pre-flight credit check reads a private, thread-safe tracker fed by every response that carries credit headers, error answers included; out-of-order responses (an older reset window, a higher remaining in the same window) are ignored, and every response logs its credits at DEBUG. An envelope with a `credit_limit` of zero is not recorded: the API answers a missing or unknown token with demo data and a `0/0` envelope from another window, which would otherwise tell the check this account has no credits. `client.utilities.user()` is asked for precisely to learn the balance, so its answer replaces the state rather than being weighed against it (#49)

### Added

- `client.utilities` resource with `status()`, `headers()` and `user()` for the `/status/`, `/headers/` and `/user/` endpoints, in every output format (#63)
- One exception class per failure, mapped from the HTTP status in a single place (SDK requirements §6.1 and §9.1): `BadRequestError` (400), `AuthenticationError` (401, never retried), `ForbiddenError` (403), `NotFoundError` (404 with an error message), `InternalError` (500: the API itself failed, never retried), `ServerError` (501 and above: the API is unavailable, retried), `NetworkError` (every `httpx` request error: connection failures, timeouts, protocol and proxy errors, wrapped with the request attached), `ParseError` (a body that is not JSON or does not match its `Content-Encoding`); `RateLimitError` now carries `retry_after` and the response on a 429 (#62)
- **404 `no_data` is no longer an error.** A valid question with an empty answer returns the empty value for the output format: a DataFrame with the model's columns and no rows, `[]` or `None` for `INTERNAL`, the `{"s": "no_data"}` body for `JSON`, a header-only file for `CSV`. In the fan-out calls a chunk or symbol with no data is left out of the merge (#62)
- Request-scoped response metadata: `marketdata.get_meta(result)` returns a `ResponseMeta` (`status_code`, `request_id`, `rate_limits`, `responses`) on every output format; for a call made of several requests (candle chunks, option symbols, retried attempts) the credits add up, the balance is the lowest count of the newest reset window, and `status_code` / `request_id` come from the last response that could have contributed to the result. `get_meta()` also takes the exception a failed call raised, so the credits a failure was billed are readable. `ResponseMeta`, `get_meta` and `UserRateLimits` are exported from the package root (#49)
- A `Lint` check on every pull request: `ruff` replaces black and isort as linter, import sorter and formatter, and adds unused-import and undefined-name detection that neither of them did. Nothing on the path to merge checked formatting or lint before, so an import left in the wrong order and a dead import both reached `main` (#85)

### Fixed

- `options.quotes()` no longer hides a per-symbol body that cannot be decoded (an HTML error page from a proxy or a captive portal) behind a fabricated empty row that read as "no options"; it raises `ParseError` with the URL, the status and a body excerpt, as every other method does, on the JSON-decoded output formats (`DATAFRAME`, `INTERNAL`, `JSON`); the CSV merge is #86 (#82)
- `stocks.candles()` and `options.quotes()` retry each request on its own instead of the whole call: a failed chunk or symbol is re-issued alone, the healthy responses are kept, and one unreachable symbol no longer re-sends (and re-bills) every other symbol on each attempt (#83)
- `options.expirations()` returns a `no_data` DataFrame with the same index as a populated one (`expirations` index, `updated` column), so concatenating results across symbols keeps the index name and gains no stray `expirations` column; the column set under a `columns=` filter is #87 (#84)
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
