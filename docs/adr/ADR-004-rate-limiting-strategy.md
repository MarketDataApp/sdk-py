# ADR-004: Rate Limiting Strategy

## Status
Accepted. Amended for v2.0 by #48 (API-credits field names) and #49 (request-scoped metadata, no public client snapshot).

## Context

The MarketData API, like most APIs, enforces rate limits to protect its infrastructure and ensure fair usage among clients. The SDK needs to:
- Track current rate limits from API responses
- Prevent requests when rate limits are exceeded
- Provide visibility to users about their current usage
- Update rate limit information after each request
- Initialize rate limits on client startup

Without a rate limiting strategy:
- Users could unknowingly exhaust their rate limit quota
- Requests would fail with 429 (Too Many Requests) errors
- Users have no visibility into their remaining quota
- Inconsistent rate limit state across multiple requests

## Decision

We implemented a **proactive rate limiting tracking and enforcement system** with the following components:

### 1. Rate Limit Data Model

```python
@dataclass
class UserRateLimits:
    credit_limit: int                # API credits in the current window
    credits_remaining: int           # API credits remaining
    reset_time: datetime.datetime    # When the credits reset
    credits_consumed: int            # API credits consumed

    def __post_init__(self):
        self.reset_time = format_timestamp(self.reset_time)

    def __repr__(self) -> str:
        return (
            f"Credits used {self.credits_consumed}/{self.credit_limit}, "
            f"remaining: {self.credits_remaining}, "
            f"reset at: {self.reset_time.isoformat()}"
        )
```

The fields follow the API-credits nomenclature of SDK requirements §8.1 (v2.0, #48): the product sells credits, not requests, and the `x-api-ratelimit-*` headers count credits. The v1 `requests_*` names were removed without aliases.

**Rationale**:
- **Dataclass**: Simple, immutable-like structure for rate limit info
- **Unix timestamp conversion**: API returns Unix timestamp, converted to `datetime` for ease of use
- **String representation**: Users can easily print and understand their rate limit status
- **All required fields**: Covers tracking consumed, remaining, limits, and reset time

### 2. Initialization Strategy

Rate limits are fetched during client initialization:

```python
class MarketDataClient:
    def __init__(self, token: str = None, logger: Logger = None):
        # ... other initialization ...
        self._rate_limits = RateLimitTracker()  # private, thread-safe
        self._setup_rate_limits()  # seed it from /user/
        
    def _setup_rate_limits(self):
        self.logger.debug("Setting up rate limits")
        self._make_request(
            method="GET",
            url="/user/",
            check_rate_limits=False,    # Don't check limits on first request
            include_api_version=False,  # Use base path
        )
```

**Rationale**:
- **Early initialization**: Ensures client has rate limit info before making requests
- **Skip validation on init**: First request shouldn't check limits (none set yet)
- **Dedicated endpoint**: `/user/` endpoint is lightweight and returns rate limit headers

### 3. Rate Limit Extraction

After every response, rate limits are extracted from HTTP headers:

```python
def _extract_rate_limits(self, response: Response) -> UserRateLimits:
    self.logger.debug("Extracting response rate limits from response headers")
    return UserRateLimits(
        credit_limit=int(response.headers["x-api-ratelimit-limit"]),
        credits_remaining=int(response.headers["x-api-ratelimit-remaining"]),
        reset_time=int(response.headers["x-api-ratelimit-reset"]),
        credits_consumed=int(response.headers["x-api-ratelimit-consumed"]),
    )
```

**Headers Used**:
- `x-api-ratelimit-limit`: API credits in the current window
- `x-api-ratelimit-remaining`: API credits remaining
- `x-api-ratelimit-consumed`: API credits consumed by this response
- `x-api-ratelimit-reset`: Unix timestamp of next reset

**Rationale**:
- **Every response**: Rate limits are updated after each request
- **Header-based**: Follows REST API best practices
- **Type conversion**: Headers are strings, converted to appropriate types

### 4. Pre-request Validation

Before making requests, rate limits are checked:

```python
def _check_rate_limits(self, raise_error: bool = True):
    if not raise_error:
        return
    state = self._rate_limits.state   # RateLimitTracker, thread-safe
    if state is None:
        self.logger.error("Rate limits cant be checked")
        raise RateLimitError("Rate limits cant be checked")
    if state.credits_remaining <= 0:
        raise RateLimitError("Rate limit exceeded")
```

**Rationale**:
- **Fail early**: Prevent requests that would be rejected by the server
- **Configurable**: `raise_error` flag allows skipping checks for specific requests (e.g., status checks)
- **Logging**: Errors are logged for debugging

### 5. Request-scoped metadata, no public snapshot (v2.0, #49)

`client.rate_limits` was removed. Under concurrent calls (the candle chunks, the option symbols, or the caller's own threads) a client-level snapshot is last-response-wins, so `credits_consumed` read from it could belong to any request. The numbers now travel with each result:

```python
import marketdata

prices = client.stocks.prices("AAPL")
meta = marketdata.get_meta(prices)      # ResponseMeta
meta.rate_limits.credits_consumed       # what this call cost
meta.rate_limits.credits_remaining      # the balance after it
meta.request_id                         # cf-ray, for support
meta.responses                          # HTTP responses behind the result
```

- **One attach point, one read point**: `api_error_handler` opens a `ContextVar` scope for the call, `_make_request` records every response into it (the fan-out resources hand the scope to their worker threads with `contextvars.copy_context().run`), and the merged `ResponseMeta` is attached to the result; `get_meta()` reads it back. Lists, dicts and CSV paths become thin subclasses (`isinstance` against `list`, `dict`, `str` still holds), pandas frames use `DataFrame.attrs["marketdata"]`, polars frames and single-object models get a `meta` attribute. `None` (a single-object endpoint with no data) carries nothing.
- **Aggregation**: `credits_consumed` adds up over the responses, `credits_remaining` is the lowest seen, `credit_limit` and `reset_time` come from the newest window, `status_code` and `request_id` from the last response. The status cache refresh is bookkeeping and is never part of a result.
- **The tracker stays private**: `RateLimitTracker` (thread-safe; discards out-of-order responses, meaning an older reset window or a higher remaining within the same window, sdk-go's rule) exists only for the pre-flight check and is fed by every response that carries credit headers, error answers included. The balance is one free call away: `client.utilities.user()`.
- **sdk-go v2 keeps `Client.RateLimits()` as a documented snapshot; sdk-py does not**, because issue #49 asks for its removal explicitly and SDK requirements §8.4 already warn that the snapshot is non-deterministic under concurrency.

**Benefits**:
- **Correct attribution**: consumed credits belong to the call that paid them
- **No shared mutable public state**: nothing to race on
- **Debugging**: the request id sits next to the data it produced

## Consequences

### Positive
- **Proactive protection**: Prevents rate limit errors before they happen
- **User visibility**: Clear understanding of rate limit usage
- **Automatic updates**: Rate limits tracked automatically without user intervention
- **Request-scoped truth**: each result carries the state its own response reported
- **Early failure**: Detect rate limit exhaustion immediately, not after server error
- **Standard headers**: Follows REST API conventions for rate limiting

### Negative
- **Additional HTTP calls**: Initialization requires an extra request to `/user/` endpoint
- **Assumes header presence**: Will fail if API doesn't include rate limit headers
- **Conservative approach**: May prevent valid requests if rate limit info is stale
- **No client-level snapshot**: callers keep the result (or call `utilities.user()`) to know the balance

### Mitigations
- The `/user/` request is lightweight and only happens once at initialization
- Error handling for missing headers with fallback behavior
- Rate limit checking is optional per request (configurable with `check_rate_limits` flag)
- The tracker is updated from every response that carries credit headers, error answers included

## Alternatives Considered

### Alternative 1: Reactive checking (fail and retry)
```python
# Let the API return 429, then catch and retry
try:
    response = client._make_request(...)
except HTTPStatusError as e:
    if e.status_code == 429:  # Rate limited
        time.sleep(...)
        return retry()
```

**Pros**: No need to track rate limits locally
**Cons**: Wastes bandwidth on failed requests, slower user experience, reactive not proactive

### Alternative 2: No rate limiting enforcement
```python
# Allow user to make requests, don't check limits
# User is responsible for managing quota
def _make_request(...):
    response = client.request(...)  # No limit checking
    return response
```

**Pros**: Simpler code, less overhead
**Cons**: Poor user experience, 429 errors at runtime, no visibility into quota

### Alternative 3: Background refresh of rate limits
```python
# Periodically refresh rate limits in background thread
import threading

def background_rate_limit_checker():
    while True:
        self.rate_limits = self._fetch_rate_limits()
        time.sleep(60)  # Check every minute

thread = threading.Thread(target=background_rate_limit_checker, daemon=True)
thread.start()
```

**Pros**: Always has fresh rate limit data
**Cons**: Threading complexity, potential race conditions, unnecessary API calls

### Alternative 4: Client-side rate limit simulation
```python
# Estimate rate limits based on requests made
# Track timestamps and estimate remaining quota
```

**Pros**: No server-side rate limit checks needed
**Cons**: Inaccurate if limits change, doesn't match actual server state

## References

- [HTTP Rate Limiting Headers](https://tools.ietf.org/html/draft-polli-ratelimit-headers)
- [GitHub API Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)
- [AWS API Rate Limiting](https://docs.aws.amazon.com/general/latest/gr/api-rate-limits.html)
- Relevant files:
  - `src/marketdata/types.py` - `UserRateLimits` dataclass
  - `src/marketdata/client.py` - Rate limit methods (`_check_rate_limits`, `_extract_rate_limits`, `_setup_rate_limits`)
  - `src/marketdata/meta.py` - `ResponseMeta`, `get_meta`, the per-call collection scope
  - `src/marketdata/rate_limit_tracker.py` - `RateLimitTracker`
  - `src/marketdata/exceptions.py` - `RateLimitError` exception
