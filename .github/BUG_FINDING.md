# Bug Finding Workflow

This document defines a systematic process for discovering bugs in
`MarketDataApp/sdk-py` through exploration and testing, before users hit them.

> **IMPORTANT: Every bug found MUST be submitted as a GitHub issue.**
>
> Do not just record bugs in markdown files, notes, or comments. Each bug must become a
> real GitHub issue:
>
> - **CLI**: `gh issue create --label "bug" --title "[Bug]: ..." --body "..."`
> - **Web**: [Create Bug Report](https://github.com/MarketDataApp/sdk-py/issues/new?template=bug.yml)
>
> A bug hunt is not complete until every discovered bug exists as a GitHub issue.

## Overview

**Purpose**: proactive bug discovery, as opposed to reactive bug processing.

- **BUG_FINDING.md** (this document): find bugs before users encounter them.
- **[ISSUE_WORKFLOW.md](./ISSUE_WORKFLOW.md)**: process bug reports that users submit.

**Workflow**: Find Bug → **Create GitHub Issue (REQUIRED)** → [ISSUE_WORKFLOW.md] → Fix

**When to use this document**:

- QA passes before releases
- Pre-release validation (see [RELEASE_PROCESS.md](./RELEASE_PROCESS.md))
- Exploratory testing sessions
- After a significant refactor
- When onboarding, to understand the edge cases

---

## Prerequisites

### Environment setup

```bash
uv sync --group dev          # installs pytest, respx, freezegun, pandas, polars, black, isort
uv pip install -e .
python --version             # 3.10 minimum; CI runs 3.10, 3.11 and 3.12

export MARKETDATA_TOKEN="your_token_here"
```

The dev group installs **both** pandas and polars. That is convenient and also a trap:
pandas always wins when both are present (`DATAFRAME_HANDLERS_PRIORITY` in
`internal_settings.py`), so the polars handler is only reached when pandas is absent.
Hunt polars bugs in a separate environment.

### Baseline verification

Confirm the suite passes before hunting. Bug finding assumes a working baseline.

```bash
./test.sh                    # uv sync && uv run pytest -n 4 --cov="marketdata"
```

344 tests pass and coverage reads 100% at the time of writing. If tests fail, fix that
first.

### Architecture

Familiarize yourself with the main components:

- `MarketDataClient` (`client.py`) — entry point. `MarketDataClient(token=..., logger=...,
  max_retries=3)`. It exposes `stocks`, `options`, `funds` and `markets`. **There is no
  `utilities` resource**; `/user/` and `/status/` are called internally only. Construction
  issues a real `GET /user/` request to seed `client.rate_limits`, unless no token is set
  — then the client logs `"No token provided, starting in demo mode"` and skips it.
- Resources (`resources/`) — each method is a plain function attached to a resource class:
  `stocks` (`prices`, `quotes`, `candles`, `earnings`, `news`), `options` (`chain`,
  `expirations`, `strikes`, `quotes`, `lookup`), `funds` (`candles`), `markets`
  (`status`).
- The decorator stack on every resource method, outermost first:
  `@api_error_handler(service=...)` → `@docs(...)` →
  `@universal_params(resource_input_type=...)`. Nothing catches: validation errors raised
  inside `universal_params` and HTTP failures raised by the client both propagate to the
  caller, after `api_error_handler` has logged the terminal failure at ERROR.
- Input models (`input_types/`) — Pydantic. Field **aliases** are what reach the API:
  `from`, `to`, `dte`, `strikeLimit`, `minBid`, `maxBidAskSpreadPct`, `minOpenInterest`,
  `52week`, `adjustsplits`, `headers`, `human`, `dateformat`.
- Output models (`output_types/`) and handlers (`output_handlers/pandas.py`,
  `output_handlers/polars.py`).
- `marketdata.exceptions` — `BaseMarketdataException` → `MarketdataHttpError` →
  {`BadRequestError`, `AuthenticationError`, `ForbiddenError`, `NotFoundError`,
  `InternalError`, `ServerError`, `NetworkError`, `ParseError`}; plus `RateLimitError`,
  `KeywordOnlyArgumentError`, `InvalidStatusDataError`, and `MinMaxValidationError` →
  {`MinMaxValueValidationError`, `MinMaxDateValidationError`}.
- `settings.py` — a **module-level singleton**, `settings = MarketDataSettings()`,
  constructed at import time from the environment and a `.env` file in the working
  directory.
- `retry.py` / `api_status.py` — tenacity retry with `Retry-After` support, gated on a
  cached `/status/` lookup refreshed every 4m30s on a background thread.

### Three Python versions, always

CI runs the suite on **3.10, 3.11 and 3.12**. A bug that appears on only one is still a
bug, and is often a more interesting one — `datetime`, `zoneinfo` and Pydantic behavior
all shift between them.

```bash
uv run --python 3.10 pytest -n 4 -q
uv run --python 3.11 pytest -n 4 -q
uv run --python 3.12 pytest -n 4 -q
```

---

## Area 1: The Exception Surface

### What can go wrong

- A resource method returning `None` or an error object instead of raising
- `support_info` missing the request id or URL, making triage impossible
- An API token leaking into a log line, an exception message, or `request_url`
- The wrong exception class for a given HTTP status
- A raw `httpx` or `json` exception reaching the caller without support context

### Test scenarios

#### 1.1 Bad token

```python
from marketdata import BaseMarketdataException, MarketDataClient

client = MarketDataClient(token="obviously-invalid-token-1234")
try:
    client.stocks.quotes("AAPL")
except BaseMarketdataException as e:
    print(e.exception_type)   # expect AuthenticationError, status_code 401
    print(e.support_info)

# Verify: the token does NOT appear anywhere in the output.
# Bug indicator: the token echoed in request_url, the message, or a log line.
```

Watch the logs as well as the exception. `client.py` logs the token through
`obfuscate_token`, which keeps the **last four characters** — that is intentional, but any
line printing the token in full is a Tier 1 security bug (see `SECURITY.md`).

```bash
MARKETDATA_LOGGING_LEVEL=DEBUG python repro.py 2>&1 | grep -i "$MARKETDATA_TOKEN"
# Bug indicator: any output at all.
```

#### 1.2 Unknown symbol

```python
try:
    client.stocks.quotes("ZZZZ_NOT_A_SYMBOL")
except BaseMarketdataException as e:
    print(e.status_code, e.message)   # the API answers 400 "Bad parameters"

# Verify: a BadRequestError with the API's status and message, consistently
# across stocks.quotes, stocks.prices, options.chain and markets.status.
# Bug indicator: a raw KeyError or TypeError from the decoder instead.
```

#### 1.3 support_info completeness

```python
try:
    client.stocks.candles("AAPL", countback=-5)
except BaseMarketdataException as e:
    print(e.support_info)
```

For an HTTP failure the block must carry all six fields:

```
--- MARKET DATA SUPPORT INFO ---
request_id:     8a1b2c3d4e5f6g7h-SJC
request_url:    https://api.marketdata.app/v1/stocks/candles/D/AAPL/?format=json&countback=-5
status_code:    422
timestamp:      2026-09-02 16:01:49
message:        countback must be a positive integer
exception_type: BadRequestError
--------------------------------
```

For a failure that never reached the API (`MinMaxDateValidationError`, `RateLimitError`)
the same six lines appear, with `request_id` / `request_url` reading `N/A` and
`status_code` reading `0`. That is by design.

**Bug indicator:** `request_id` reading `N/A` when the response genuinely carried a
`cf-ray` header, a `status_code` of `0` on a real HTTP failure, or the token appearing in
`request_url`.

#### 1.4 Every exception type is reachable and correct

```python
# Walk the hierarchy and confirm each type is produced by the condition it names.
from marketdata.exceptions import (
    BadRequestError, AuthenticationError, ForbiddenError, NotFoundError,
    InternalError, ServerError, NetworkError, ParseError, RateLimitError,
    KeywordOnlyArgumentError, InvalidStatusDataError,
    MinMaxDateValidationError, MinMaxValueValidationError,
)
```

`ServerError` (501 and above) and `NetworkError` are what the retry loop retries on.
Everything else is terminal: a 500 is an `InternalError` (the API itself failed, retrying
will not help), and a 404 without `errmsg` is not an exception at all but an empty
result. Getting these the wrong way round means either an unretried transient failure or
four pointless retries against a 404.

### Red flags

- A resource method returning `None`, or anything other than the requested output, on failure
- A bare `httpx.HTTPStatusError` or `json.JSONDecodeError` reaching the caller
- An API token visible anywhere in output
- `support_info` lines missing for an HTTP failure
- An exception class that does not describe what happened

### Pass/fail criteria

| Scenario | Pass | Fail |
|---|---|---|
| Bad token | `AuthenticationError` raised, token obfuscated | Raw exception, or token leaked |
| Unknown symbol | `BadRequestError` with the API's status and message | `KeyError` / `TypeError` from the decoder |
| No data | An empty result for the output format, no exception | A `NotFoundError`, or a decoder crash on the `no_data` body |
| support_info | All six fields on every SDK exception | Blank or missing fields |
| Exception mapping | Retryable vs terminal correctly split | 5xx treated as terminal, or 4xx retried |

---

## Area 2: Parameter Aliases and Silently Dropped Filters

**This is the highest-yield area in this SDK.** Four of the five bugs fixed in `1.3.0`
(#30, #23, #24, #19) were parameters that never reached the API, or reached it wrongly.
The failure mode is silent: the request succeeds, the data comes back unfiltered, and
nothing anywhere reports a problem.

### What can go wrong

- A Pydantic field with a missing or misspelled `alias`, so the API never sees the filter
- A value serialized in a form the API rejects or ignores (a `float` where an `int` is
  required, a `bool` as `True` rather than `true`, a `date` in the wrong format)
- A parameter excluded by `_build_url`'s `excluded_params` when it should be sent
- An unset parameter sent anyway, with an invented default

### Test scenarios

#### 2.1 Every filter reaches the query string

Assert on the URL the SDK actually built, not on the data that came back:

```python
import respx, httpx
from marketdata import MarketDataClient

with respx.mock(base_url="https://api.marketdata.app") as mock:
    mock.get("/user/").mock(return_value=httpx.Response(200, json={}, headers={
        "x-api-ratelimit-limit": "100", "x-api-ratelimit-remaining": "99",
        "x-api-ratelimit-reset": "60", "x-api-ratelimit-consumed": "1",
    }))
    route = mock.get("/v1/options/chain/AAPL/").mock(
        return_value=httpx.Response(200, json={"s": "ok"}))

    client = MarketDataClient(token="test")
    client.options.chain(
        "AAPL",
        days_to_expiration=30,
        strike_limit=5,
        min_open_interest=100,
        max_bid_ask_spread_pct=0.05,
        side="call",
    )

    params = route.calls.last.request.url.params
    print(dict(params))
    # Verify: dte=30, strikeLimit=5, minOpenInterest=100,
    #         maxBidAskSpreadPct=0.05, side=call
    # Bug indicator: a parameter you passed is absent from the dict.
```

Repeat this for every input model in `input_types/`. Walking
`Model.model_fields[name].alias` and asserting the alias appears in the URL for each field
turns this into one table-driven test.

#### 2.2 Unset stays unset

```python
client.stocks.prices("AAPL")
print(dict(route.calls.last.request.url.params))

# Verify: parameters nobody set are ABSENT, not sent with a guessed default.
# `format=json` is expected; columns=, human=false, mode= are not.
```

#### 2.3 Types the API actually accepts

```python
client.options.chain("AAPL", strike_limit=5)      # int
client.options.chain("AAPL", delta=0.30)          # float
client.options.chain("AAPL", weekly=True)         # bool → how is it encoded?
client.options.chain("AAPL", expiration="all")    # Literal
```

The API rejects some encodings and silently ignores others. A rejection is loud and gets
fixed; an ignore is what shipped as #24 and #30. Check the request, and where you have a
live token, check that the response actually changed.

### Pass/fail criteria

| Scenario | Pass | Fail |
|---|---|---|
| Filter reaches the API | Alias present with the right value | Parameter absent |
| Unset parameter | Omitted from the URL | Sent with an invented default |
| Value encoding | Accepted and honored by the API | Accepted and ignored |

---

## Area 3: Output Format Parity

Four formats are meant to be four views of one response: `DATAFRAME` (default),
`INTERNAL`, `JSON`, `CSV`. Each has its own branch at the bottom of every resource
method, so they drift independently.

### What can go wrong

- A field present in one format and missing from another
- `columns=` honored by one format and ignored by another (this was #23)
- Timestamps converted in one format and left as integers in another
- `use_human_readable=True` changing the field names in one format only

### Test scenarios

#### 3.1 Same call, four formats

```python
from marketdata import MarketDataClient, OutputFormat

client = MarketDataClient()
kwargs = dict(symbol="AAPL", resolution="D", countback=5)

df       = client.stocks.candles(**kwargs)
internal = client.stocks.candles(**kwargs, output_format=OutputFormat.INTERNAL)
raw      = client.stocks.candles(**kwargs, output_format=OutputFormat.JSON)
path     = client.stocks.candles(**kwargs, output_format=OutputFormat.CSV)

# Verify: same row count, same values, same instants in all four.
# Bug indicator: DATAFRAME dropping or reordering rows that JSON contains.
```

#### 3.2 Column projection in every format

```python
for fmt in (OutputFormat.DATAFRAME, OutputFormat.INTERNAL, OutputFormat.JSON):
    result = client.options.expirations("AAPL", columns=["expirations"], output_format=fmt)
    print(fmt, result)

# Verify: the projection is applied — or deliberately ignored — consistently.
# `_validate_user_universal_params` clears `columns` for INTERNAL on purpose;
# confirm that is still the intent and that it is documented.
# Bug indicator: an empty result rather than a projected one (the shape of #23).
```

#### 3.3 human-readable field names

```python
result = client.stocks.candles("AAPL", countback=5, use_human_readable=True,
                               output_format=OutputFormat.INTERNAL)
# Verify: StockCandlesHumanReadable, with Date/Open/High/Low/Close/Volume.
# Bug indicator: a KeyError from a name containing a space that was never
# normalized (options.chain rewrites "k v" → "k_v"; do the others?).
```

### Pass/fail criteria

| Scenario | Pass | Fail |
|---|---|---|
| Four formats | Identical data | Rows or fields differ |
| Column projection | Consistent across formats | Empty result in one |
| Human-readable | Renamed fields decode cleanly | `KeyError` on a spaced name |

---

## Area 4: CSV Output and File Handling

`OutputFormat.CSV` is the only output that touches the filesystem, and its validation
lives in a Pydantic `field_validator` rather than in the resource method.

### What can go wrong

- Writing outside the intended directory, or overwriting an existing file
- The `output/` directory appearing for non-CSV requests, or when the caller supplied a
  filename (it must only be created when a default-named CSV is written)
- The returned path not being the file that was written
- Multi-part responses (auto-chunked candles) producing a CSV with repeated headers

### Test scenarios

#### 4.1 Filename validation

```python
from pathlib import Path
from marketdata import MarketDataClient, OutputFormat

client = MarketDataClient()

for bad in ("out.txt", "nope/out.csv"):
    try:
        client.stocks.prices("AAPL", output_format=OutputFormat.CSV, filename=bad)
    except Exception as e:
        print(type(e).__name__, e)
    print(type(result.error).__name__, result.error)

# Verify: each raises a Pydantic ValidationError whose message names the
# offending path (the SDK's own classes are not involved in input validation).
# Bug indicator: a bare ValueError with no path, or the call succeeding.
```

#### 4.1b A custom filename is honored

```python
path = client.stocks.prices("AAPL", output_format=OutputFormat.CSV, filename="mine.csv")
print(path)   # <cwd>/mine.csv, absolute
```

`BaseResource._validate_user_universal_params` merges settings < client defaults < call
and only defaults `filename` when nobody supplied one (#60: it used to force `None`
unconditionally, so the caller's validated filename was replaced by a timestamped path in
`output/` and the call still looked successful).

**Verify on every pass**, and check the same for the other resources: the file that gets
written must be the file the caller asked for, the returned path must be the file that
was written, and no `output/` directory appears when a filename was given.

#### 4.2 The default path

```python
path = client.stocks.prices("AAPL", output_format=OutputFormat.CSV)
print(path)          # <cwd>/output/YYYYmmdd_HHMMSS_ffffff.csv, absolute
print(Path(path).exists(), Path(path).read_text()[:200])

# Verify: the returned absolute path exists and holds the CSV.
# Note: `output/` is created in the caller's current working directory only when a
# CSV is actually written there; JSON/DataFrame/INTERNAL requests never create it
# (#43). The write is an exclusive create, so a path that appears between
# validation and the write fails the call instead of being overwritten.
```

#### 4.3 Chunked candles merge

```python
import datetime
path = client.stocks.candles(
    "AAPL", resolution="1H",
    from_date=datetime.datetime.now() - datetime.timedelta(days=800),
    to_date=datetime.datetime.now(),
    output_format=OutputFormat.CSV,
)
# An intraday range over 365 days splits into concurrent requests and merges.
# Verify: one header row, chronological order, no duplicate timestamps at the
# chunk boundary.
```

### Pass/fail criteria

| Scenario | Pass | Fail |
|---|---|---|
| Bad filename | Error result naming the offending path | Unhandled exception, or overwrite |
| Custom filename | The caller's file is written | A timestamped `output/` file instead |
| Default path | Existing absolute path, valid CSV | Missing file, or wrong path returned |
| Chunked merge | One header, ordered, deduplicated | Repeated headers or gaps |

---

## Area 5: Dates, Times and Timezones

### What can go wrong

- The three `DateFormat` values decoding to different instants
- Timestamps interpreted as UTC when the API sends US/Eastern, or the reverse
- A `date` accepted where a `datetime` is required, or the reverse
- The host machine's timezone leaking into a result

### Test scenarios

#### 5.1 Date format round-trip

```python
from marketdata import DateFormat, OutputFormat

for df in (DateFormat.TIMESTAMP, DateFormat.UNIX, DateFormat.SPREADSHEET):
    candles = client.stocks.candles("AAPL", countback=5, date_format=df,
                                    output_format=OutputFormat.INTERNAL)
    print(df, candles)

# Verify: every encoding decodes to the SAME instants.
# Bug indicator: a format that raises, or rows shifted by hours between formats.
# `utils.format_timestamp` treats values between 0 and 60000 as spreadsheet
# dates — check where that heuristic misfires.
```

#### 5.2 Intraday range splitting

```python
import datetime
candles = client.stocks.candles(
    "AAPL", resolution="1H",
    from_date="2023-01-01", to_date="2025-01-01",   # str input is accepted
    output_format=OutputFormat.INTERNAL,
)
# `split_dates_by_timeframe` cuts this into 365-day ranges and runs them through
# a ThreadPoolExecutor.
# Verify: the boundary candle appears exactly once. The ranges are disjoint
# calendar days: each chunk ends the day before the next one starts (#51).
# Bug indicator: a duplicated candle at each year boundary.
```

#### 5.3 Host timezone independence

```bash
TZ=Pacific/Kiritimati uv run pytest -n 4 -q
TZ=Pacific/Niue       uv run pytest -n 4 -q
```

Two runs, about 25 hours of UTC offset apart. Any test that passes under one and fails
under the other has an unstated dependency on the host clock. Worth running on every QA
pass — CI runners are all UTC, so these bugs stay invisible there.

### Pass/fail criteria

| Scenario | Pass | Fail |
|---|---|---|
| Date formats | Identical decoded instants | Format-dependent values |
| Range splitting | Each candle once, in order | Duplicate at the boundary |
| Host timezone | Identical results under any `TZ` | Results vary with `TZ` |

---

## Area 6: pandas and polars Parity

Two independent handlers implement one contract. Nothing forces them to agree, and pandas
hides polars whenever both are installed.

### Test scenarios

#### 6.1 Same result from both handlers

```python
# repro.py
from marketdata import MarketDataClient
df = MarketDataClient().stocks.candles("AAPL", countback=5)
print(type(df))
print(df)
```

Run it in two clean environments — one per handler, because pandas hides polars whenever
both are installed:

```bash
cd "$(mktemp -d)" && python -m venv .venv && . .venv/bin/activate
pip install "marketdata-sdk-py[pandas]" && python repro.py

cd "$(mktemp -d)" && python -m venv .venv && . .venv/bin/activate
pip install "marketdata-sdk-py[polars]" && python repro.py
```

Compare: same rows, same column names, same index column, same dtypes for the timestamp
column. The pandas handler indexes candles by `t`/`Date` — confirm polars expresses the
same intent, given that polars has no index.

#### 6.2 Neither installed

```bash
cd "$(mktemp -d)" && python -m venv .venv && . .venv/bin/activate
pip install marketdata-sdk-py          # no extras — no pandas, no polars
python -c "
from marketdata import MarketDataClient
MarketDataClient().stocks.prices('AAPL')"
```

Expect a `ValueError("No dataframe output handler found")` to be raised — the default
output format needs a DataFrame library that a bare `pip install marketdata-sdk-py` does
not bring in.

**Bug indicator:** an unhandled `ImportError`, or a message that does not tell the user to
install pandas or polars.

#### 6.3 The handler cache

`_try_get_handler` is wrapped in `@lru_cache(maxsize=1)` but is called once per handler
name in priority order, so two names compete for one slot and each lookup can evict the
other. The cache also lives for the whole process. Confirm that a handler resolved once is
not stale afterwards — for example when a test removes pandas from `sys.modules` and
expects the polars path to be taken.

---

## Area 7: Configuration Cascade

The documented precedence is: **per-method keyword > `client.default_params` > environment
variable / `.env` > SDK default**, resolved in
`BaseResource._validate_user_universal_params`.

### What can go wrong

- A per-method keyword losing to a client-level default (inverted precedence)
- An environment variable overriding an explicit in-code setting
- `.env` being read at import time, so a variable set later has no effect

### Test scenarios

#### 7.1 Method beats client

```python
from marketdata import MarketDataClient, DateFormat
from marketdata.input_types.base import UserUniversalAPIParams

client = MarketDataClient()
client.default_params = UserUniversalAPIParams(date_format=DateFormat.UNIX)

client.stocks.quotes("AAPL", date_format=DateFormat.TIMESTAMP)
# Verify: the URL carries dateformat=timestamp, NOT unix.
```

#### 7.2 Client beats environment

```bash
MARKETDATA_DATE_FORMAT=unix python repro.py    # with date_format set in code
```

#### 7.3 The settings singleton

```python
import os
os.environ["MARKETDATA_BASE_URL"] = "https://example.invalid"
from marketdata import MarketDataClient      # imported AFTER the assignment
print(MarketDataClient().base_url)
```

`settings = MarketDataSettings()` is evaluated at **import** time. Setting a variable after
the import has no effect, and a `.env` file is read relative to the working directory at
that moment. Confirm this is the documented behavior and that it is stated in the README —
a user who calls `os.environ[...] = ...` in a notebook after importing will otherwise see
their setting ignored with no error.

### Pass/fail criteria

| Scenario | Pass | Fail |
|---|---|---|
| Method vs client | Method wins | Client default wins |
| Client vs environment | Client value wins | Environment wins |
| Late environment change | Documented as ineffective | Silently ignored, undocumented |

---

## Area 8: Retries, Rate Limits and the Status Cache

### What can go wrong

- A transient 5xx not retried, or a terminal 4xx retried four times
- `Retry-After` parsed wrongly, producing a huge or negative sleep
- The rate-limit snapshot going stale, or blocking valid requests
- The background `/status/` refresh thread racing, or leaking between calls

### Test scenarios

#### 8.1 Retry classification

```python
# With respx, return 503 twice then 200, and assert three calls were made.
# Then return 404 and assert exactly one call was made.
# max_retries defaults to 3, so up to 4 attempts total (attempts = max_retries + 1).
```

#### 8.2 Retry-After

```python
# Return 503 with Retry-After: 2, then with an HTTP-date, then with garbage.
# `retry.parse_retry_after` must yield 2.0, a positive delta, and None.
# Bug indicator: a non-finite float, a negative sleep, or an unhandled parse error.
```

#### 8.3 Rate-limit exhaustion

```python
client = MarketDataClient(token="...")
client.rate_limits.requests_remaining = 0
result = client.stocks.prices("AAPL")

# Verify: a RateLimitError inside an error result, and NO HTTP request made.
# Bug indicator: the request going out anyway, or an unhandled raise.
```

Also confirm `client.rate_limits` advances across successive real calls, and that the
`/status/` and `/user/` requests do **not** move it — they are issued with
`populate_rate_limits=False` and `check_rate_limits=False` on purpose.

#### 8.4 Status cache under concurrency

```python
# Fire 20 concurrent calls that all trigger a retryable ServerError (501 and above).
# Verify: one background refresh thread at a time (`_refresh_in_flight`), no
# deadlock, and `_refresh_in_flight` reset even when the refresh raises.
```

`API_STATUS_DATA` is a module-level singleton shared by every client in the process. Two
clients pointed at different `MARKETDATA_BASE_URL` values share one status cache — check
whether that can mislead one of them.

### Pass/fail criteria

| Scenario | Pass | Fail |
|---|---|---|
| Retry classification | 5xx retried, 4xx not | Either side wrong |
| `Retry-After` | Finite, non-negative, or `None` | Negative, infinite, or a raise |
| Rate limits | Blocks at zero, no request sent | Request sent anyway |
| Status refresh | One thread, flag always reset | Deadlock or stuck flag |

---

## Area 9: The Keyword-Only Calling Convention

Only `symbol`, `symbols` and `lookup` may be passed positionally
(`ALLOWED_POSITIONAL_PARAMS`). Everything else must be a keyword.

### Test scenarios

```python
from marketdata import MarketDataClient, OutputFormat

client = MarketDataClient()

client.stocks.prices("AAPL")                                   # ok
client.stocks.prices(symbols="AAPL")                           # ok
client.stocks.prices("AAPL", output_format=OutputFormat.JSON)  # ok
result = client.stocks.prices("AAPL", OutputFormat.JSON)       # rejected
```

The last call raises `KeywordOnlyArgumentError` before any request is made, as the README
documents. Bug indicator: the call going through with the positional value silently
ignored, or a different exception class.

Check also that `client.markets.status()` accepts **no** positional argument at all, and
that `client.options.lookup("AAPL 20-12-2024 150.0 call")` accepts one.

---

## Reporting What You Find

For every bug, open an issue immediately. Include:

1. The area and scenario number from this document
2. Minimal reproduction code, complete with imports and `MarketDataClient(...)`
3. Expected versus actual behavior
4. The `support_info` block when an error result was involved
5. SDK version, `python --version`, the output format used, and which DataFrame library
   was installed
6. Which Python versions it reproduces on

```bash
gh issue create --label "bug" \
  --title "[Bug]: options.chain drops min_open_interest from the request" \
  --body "$(cat <<'EOF'
**Area**: 2.1 Every filter reaches the query string
**Reproduces on**: Python 3.10, 3.11, 3.12
...
EOF
)"
```

Then hand off to [ISSUE_WORKFLOW.md](./ISSUE_WORKFLOW.md).

---

## Coverage Note

`pytest --cov="marketdata"` reports **100%**, so every line already has *a* test. That is
exactly why this document targets behavior rather than reachability: full coverage proves
each line ran, not that it did the right thing.

Two blind spots make that gap wider here than the number suggests:

- **The unit suite mocks HTTP through `respx`.** It proves the SDK agrees with the
  fixtures in `src/tests/data/` — not that the fixtures still match what
  `api.marketdata.app` sends. The live suite in `src/tests/integration/` (one test per
  endpoint, run on every pull request; see [RELEASE_PROCESS.md](./RELEASE_PROCESS.md) §7)
  is the check against the real API, but it asserts shapes, not values: a parameter the
  API silently ignores can still look identical to one it honors. **Every bug hunt should
  include at least one pass against the live API with a real token.**
- **Nothing enforces the number.** There is no `--cov-fail-under`, no `codecov.yml`, and
  no coverage status check in branch protection. Coverage can fall without failing a
  build.

The bugs left to find here are wrong answers on covered lines, disagreements between the
two DataFrame handlers, drift between the mocked fixtures and the live API, and
assumptions about the host environment — none of which a coverage number can see.
