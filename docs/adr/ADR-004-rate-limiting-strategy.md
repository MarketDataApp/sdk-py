# ADR-004: Rate Limiting Strategy

## Status
Accepted

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
    requests_limit: int              # Total requests allowed
    requests_remaining: int          # Requests remaining in current window
    requests_reset: datetime.datetime # When the limit resets
    requests_consumed: int           # Total requests consumed

    def __post_init__(self):
        self.requests_reset = format_timestamp(self.requests_reset)

    def __repr__(self) -> str:
        return f"Rate used {self.requests_consumed}/{self.requests_limit},\
            remaining: {self.requests_remaining} credits,\
            next reset: {self.requests_reset.isoformat()}"
```

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
        self.rate_limits = None
        self._setup_rate_limits()  # Fetch initial rate limits
        
    def _setup_rate_limits(self):
        self.logger.debug("Setting up rate limits")
        self._make_request(
            method="GET",
            url="/user/",
            check_rate_limits=False,    # Don't check limits on first request
            include_api_version=False,  # Use base path
            populate_rate_limits=True   # Extract rate limit headers
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
        requests_limit=int(response.headers["x-api-ratelimit-limit"]),
        requests_remaining=int(response.headers["x-api-ratelimit-remaining"]),
        requests_reset=int(response.headers["x-api-ratelimit-reset"]),
        requests_consumed=int(response.headers["x-api-ratelimit-consumed"]),
    )
```

**Headers Used**:
- `x-api-ratelimit-limit`: Total requests allowed in current window
- `x-api-ratelimit-remaining`: Requests remaining
- `x-api-ratelimit-consumed`: Total requests consumed
- `x-api-ratelimit-reset`: Unix timestamp of next reset

**Rationale**:
- **Every response**: Rate limits are updated after each request
- **Header-based**: Follows REST API best practices
- **Type conversion**: Headers are strings, converted to appropriate types

### 4. Pre-request Validation

Before making requests, rate limits are checked:

```python
def _check_rate_limits(self, raise_error: bool = True):
    if raise_error and self.rate_limits is None:
        self.logger.error("Rate limits cant be checked")
        raise RateLimitError("Rate limits cant be checked")

    if raise_error and self.rate_limits.requests_remaining <= 0:
        raise RateLimitError("Rate limit exceeded")
```

**Rationale**:
- **Fail early**: Prevent requests that would be rejected by the server
- **Configurable**: `raise_error` flag allows skipping checks for specific requests (e.g., status checks)
- **Logging**: Errors are logged for debugging

### 5. User Access to Rate Limits

Users can access current rate limit information:

```python
client = MarketDataClient()

# Access rate limits object
rate_limits = client.rate_limits

# Access individual fields
print(f"Limit: {rate_limits.requests_limit}")
print(f"Remaining: {rate_limits.requests_remaining}")
print(f"Consumed: {rate_limits.requests_consumed}")
print(f"Reset at: {rate_limits.requests_reset}")

# Or use formatted string
print(rate_limits)  
# Output: "Rate used X/Y, remaining: Z credits, next reset: ISO timestamp"
```

**Benefits**:
- **Transparency**: Users can see their quota and plan requests accordingly
- **Predictability**: Users know when limits will reset
- **Debugging**: Useful for troubleshooting rate limit issues

## Consequences

### Positive
- **Proactive protection**: Prevents rate limit errors before they happen
- **User visibility**: Clear understanding of rate limit usage
- **Automatic updates**: Rate limits tracked automatically without user intervention
- **Centralized tracking**: Single source of truth for rate limit state
- **Early failure**: Detect rate limit exhaustion immediately, not after server error
- **Standard headers**: Follows REST API conventions for rate limiting

### Negative
- **Additional HTTP calls**: Initialization requires an extra request to `/user/` endpoint
- **Assumes header presence**: Will fail if API doesn't include rate limit headers
- **Conservative approach**: May prevent valid requests if rate limit info is stale
- **Complex state**: Need to maintain rate_limits object in client

### Mitigations
- The `/user/` request is lightweight and only happens once at initialization
- Error handling for missing headers with fallback behavior
- Rate limit checking is optional per request (configurable with `check_rate_limits` flag)
- Rate limits are updated after every successful response

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
  - `src/marketdata/exceptions.py` - `RateLimitError` exception
