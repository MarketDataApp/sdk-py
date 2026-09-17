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

### Changed (BREAKING)

- `options.chain(delta=...)` checks a number before it sends it, the way it checks `strike`, and keeps it as the text it sends. A `bool`, a NaN, an infinity and a number a float cannot hold now raise `ValidationError` before any request, where they used to be sent: `delta=nan` came back as the whole chain, since the API reads it as no filter, and `delta=True` was sent as `1.0`. `OptionsChainInput.delta` holds that text (`"0.5"`) instead of a `float` (#101). Migration: pass a finite number, a `DeltaFilter`, or `delta=None` for no filter; code that reads `OptionsChainInput(...).delta` gets the text sent to the API, and `float()` turns a plain number back.

### Changed

- **BREAKING**: every request now uses a 2 second connect timeout and 99 seconds for each read, write and connection-pool wait, instead of one 60 second bound shared by all four (SDK requirements §10). Those are per-operation bounds, as httpx defines them, not a deadline for the whole call. The value is fixed and not configurable, and `MarketDataClient._make_request` no longer takes a `timeout` argument: a call that should give up sooner is cancelled by the caller rather than given a shorter bound, so an SDK request cannot outlive the API's own limit. A connect or read timeout is still a `NetworkError` and is still retried (#64)
- Retries follow SDK requirements §9.2: only `ServerError` (501 and above) and `NetworkError` are retried; `InternalError` (500), every 4xx, a 429 and a `NetworkError` the client itself caused (a base URL without a scheme, a malformed request, a proxy that refuses the connection) are final (#62)
- Every SDK exception now carries the full support context (`request_id`, `request_url`, `status_code`, `timestamp`, `message`, `exception_type`) and a `support_info` block; non-HTTP failures report `N/A` / `0` for the request fields (#20)
- All exception classes are re-exported from the package root (`from marketdata import BaseMarketdataException, ...`) (#20)
- `options.quotes()` raises `MarketdataHttpError` instead of returning an error object when none of the per-symbol responses is usable (#20)
- `stocks.quotes()` now requests `stocks/quotes/?symbols=...` instead of the deprecated `stocks/bulkquotes/`; the method, its parameters and its output are unchanged (#74)
- **BREAKING**: `UserRateLimits` speaks in API credits, as the product does (SDK requirements §8.1): `requests_limit` → `credit_limit`, `requests_remaining` → `credits_remaining`, `requests_consumed` → `credits_consumed`, `requests_reset` → `reset_time`. The old names are gone, with no aliases; its string form now reads `Credits used X/Y, remaining: Z, reset at: <ISO timestamp>` (#48)
- The pre-flight credit check reads a private, thread-safe tracker fed by every response that carries credit headers, error answers included; out-of-order responses (an older reset window, a higher remaining in the same window) are ignored, and every response logs its credits at DEBUG. An envelope with a `credit_limit` of zero is not recorded: the API answers a missing or unknown token with demo data and a `0/0` envelope from another window, which would otherwise tell the check this account has no credits. `client.utilities.user()` is asked for precisely to learn the balance, so its answer replaces the state rather than being weighed against it (#49)

### Added

- `StrikeFilter` builds the `strike` filter of `options.chain` from its shapes instead of from a hand-written string: `exact`, `any_of`, `between`, `at_least`, `at_most`, `above`, `below`, and `expression` for anything the others do not name, the way sdk-go and sdk-csharp give them. `DeltaFilter` does the same for `delta`, which the API reads with the same grammar, with `nearest` in place of `exact`: the API answers a single delta with the contract nearest to it. Both parameters also take a plain `int`, `float` or `Decimal` now, which `strike` refused before while the public docs typed it `float`, so a strike read from an INTERNAL chain can be passed straight back. A negative **number** is refused rather than sent: the API reads a number by its absolute value, so `strike=-250` used to answer with the strikes at `250` and no error. A string is still passed through as written, since it is the expression form and the API is what reads it. A negative delta is kept, since there the absolute value is the documented filter and both sides come back either way. A number travels as plain digits, never in exponent form: the API reads a query of `delta=0.00005`, and answers `delta=5e-05` with a `400`, since it splits that text at its minus. A number a float cannot hold is refused, since the API reads each one with `float()` and would take it for an infinity or for 0 (#101)
- The API's IP headers, for accounts that restrict access by IP (#44). A 403 that blocks an address raises `ForbiddenError` with `authorized_ip`, the address the account is authorized for, taken from `X-API-Authorized-IP` and repeated in the message, so a caller who prints the error knows what to allow. `marketdata.get_meta(result).detected_ip` is the address the call came from, taken from `X-API-Detected-IP` on every answer the API serves. Both read `None` when the API sent no header: an account allowed to call from several addresses, a staff token, the Sheets add-on, or an address it could not resolve. The legacy `X-API-BLOCKED-IP` is not read: the API is removing it (MarketData-App/api#202)
- `client.utilities` resource with `status()`, `headers()` and `user()` for the `/status/`, `/headers/` and `/user/` endpoints, in every output format (#63)
- One exception class per failure, mapped from the HTTP status in a single place (SDK requirements §6.1 and §9.1): `BadRequestError` (400), `AuthenticationError` (401, never retried), `ForbiddenError` (403), `NotFoundError` (404 with an error message), `InternalError` (500: the API itself failed, never retried), `ServerError` (501 and above: the API is unavailable, retried), `NetworkError` (every `httpx` request error: connection failures, timeouts, protocol and proxy errors, wrapped with the request attached), `ParseError` (a body that is not JSON or does not match its `Content-Encoding`); `RateLimitError` now carries `retry_after` and the response on a 429 (#62)
- **404 `no_data` is no longer an error.** A valid question with an empty answer returns the empty value for the output format: a DataFrame with the model's columns and no rows, `[]` or `None` for `INTERNAL`, the `{"s": "no_data"}` body for `JSON`, a header-only file for `CSV`. In the fan-out calls a chunk or symbol with no data is left out of the merge (#62)
- Request-scoped response metadata: `marketdata.get_meta(result)` returns a `ResponseMeta` (`status_code`, `request_id`, `rate_limits`, `responses`) on every output format; for a call made of several requests (candle chunks, option symbols, retried attempts) the credits add up, the balance is the lowest count of the newest reset window, and `status_code` / `request_id` come from the last response that could have contributed to the result. `get_meta()` also takes the exception a failed call raised, so the credits a failure was billed are readable. `ResponseMeta`, `get_meta` and `UserRateLimits` are exported from the package root (#49)
- A `Lint` check on every pull request: `ruff` replaces black and isort as linter, import sorter and formatter, and adds unused-import and undefined-name detection that neither of them did. Nothing on the path to merge checked formatting or lint before, so an import left in the wrong order and a dead import both reached `main` (#85)

### Fixed

- `options.quotes()` no longer hides a per-symbol body that cannot be decoded (an HTML error page from a proxy or a captive portal) behind a fabricated empty row that read as "no options"; it raises `ParseError` with the URL, the status and a body excerpt, as every other method does (#82, CSV output in #86)
- `stocks.candles()` and `options.quotes()` retry each request on its own instead of the whole call: a failed chunk or symbol is re-issued alone, the healthy responses are kept, and one unreachable symbol no longer re-sends (and re-bills) every other symbol on each attempt (#83)
- `options.expirations()` returns a `no_data` DataFrame with the same index as a populated one (`expirations` index, `updated` column), so concatenating results across symbols keeps the index name and gains no stray `expirations` column (#84)
- The CSV output of `stocks.candles()` and `options.quotes()` is merged from the answers themselves: the file keeps the header the API sent (the requested `columns`, the human-readable names) and every row of every chunk or symbol; it used to compare each body against the model's field list and silently drop every body that differed, so a `columns=` request or a human-readable `options.quotes()` produced a header-only file, and an undecodable body (an HTML error page) vanished without a word. Such a body now raises `ParseError`, and so does a body the `csv` module cannot read (a field past its size limit), which escaped as a raw `csv.Error` (#86)
- The `no_data` DataFrame and the header-only CSV carry the requested columns under a `columns=` filter, in request order, as a populated answer does; API names select the human-readable twins under `use_human_readable=True`, and under `add_headers=False` the empty CSV is an empty file. Known limit: the API's own aliases (`open` for `o`, `price`, `date`) are not translated, because the accepted set depends on the endpoint, so filtering on one of those still gives an empty frame of a different shape than the populated answer (#87)
- A `404` `no_data` whose body is not JSON (a CDN or a proxy answering the 404 without one) returns the empty result on the JSON output too, instead of raising `ParseError` there while the other three formats returned their empty value: the output format never decides whether a call raises (#87)
- The CSV fan-out merge compares the headers of two answers through the same case- and space-insensitive key it validates them with, so the same column spelled differently no longer fails a valid request; a different column order is still refused (#86)
- The CSV error envelope is recognised whatever the case or padding of its `s` marker under `add_headers=False`, matched through the same key the header row uses; a message lost there made a `404` read as the empty answer again. An `errmsg` that is not a string still raises, and reports the raw body instead of Python's repr of the decoded value. The error envelope and the fan-out merge read a CSV body the same way: a body whose lines end in a lone CR is read as rows instead of defeating the reader, and a byte order mark at the start of a body is dropped before the parse, so it no longer breaks the quoting of the first value (#91)
- The API renders the CSV empty answer as a `200` with a placeholder body (`0` and an empty cell) instead of a `404` (MarketData-App/api#422); every resource used to write that placeholder into the CSV file. The SDK now recognises it as the empty answer: a header-only file, and a chunk or symbol left out of the fan-out merge; on JSON output the result is the canonical `{"s": "no_data"}` (#89)
- A `404` carrying an error message is a `NotFoundError` on every output format. With `OutputFormat.CSV` the API renders the message as an `s,errmsg` table, which only the JSON decoder could read, so an unknown symbol raised on JSON output and wrote a header-only file on CSV output. Error messages on the other statuses now read the same on both formats too, and the headerless envelope of `add_headers=False` is read as well. In the fan-out calls this means a symbol or chunk the API answers with a message fails the whole call on CSV output, as it already did on the other formats; a part with no data and no message still simply contributes no rows (#91)
- `stocks.candles()` no longer raises `KeyError` under `columns=` on DataFrame and JSON output: the chunks are merged on the model's columns among those the API sent, in the order it sent them, which is the request order and the order of the empty result. `options.quotes()` merges its symbols by the same rule; a symbol lacking a column another one carries used to shift the rows of every symbol after it (the next symbol's bid on its row), drop the column for every symbol when the first one lacked it, or raise a bare `KeyError` on the human-readable model. On both, a JSON body that is not an object, carries none of the resource's fields, lacks a column another answer carries, or has a column that is not a list as long as the others raises `ParseError` naming that request (#90)
- The pre-flight credit check no longer refuses requests it cannot judge (#42). It used to raise `RateLimitError` when the balance was unknown, a state the tracker could only leave by making a request, so a client that started without usable credit headers refused every call for the rest of its life. It also ignored the reset time, so one exhausted window refused every later request even after the API would have accepted them. Now an unknown balance and an exhausted window that has already reset both let the request through, and a refusal carries `retry_after`, the seconds until the balance resets
- `UserRateLimits.reset_time` always carries an offset, so the reset the SDK compares against the clock is the one it prints. A value that arrives without one is read as US/Eastern, the timezone the SDK renders every timestamp in; read as UTC it put the refusal hours from where it belonged. A wall time that a daylight-saving change repeats or skips names no single instant and now raises `ValueError` instead of silently landing an hour away (#42)
- A pre-flight credit refusal writes one ERROR line instead of two: the SDK's one-line-per-terminal-failure rule already covers it, and the second line made alerting that counts ERROR records read one refusal as two (#42)
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
