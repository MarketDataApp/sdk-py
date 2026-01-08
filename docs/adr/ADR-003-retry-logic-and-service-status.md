# ADR-003: Retry Logic and Service Status Checking

## Status
Accepted

## Context

The SDK must interact with the MarketData API, which like any cloud service can experience:
- Transient errors (timeouts, rate limiting, unstable connection)
- Specific service unavailability
- Service degradation

Without an intelligent retry strategy:
- Users experience failures that could have been automatically resolved
- No differentiation between permanent and transient errors
- The SDK could saturate the server with retries without exponential backoff
- No visibility into the current state of services

## Decision

We implemented a three-layer strategy:

### Layer 1: Custom Exception Hierarchy

We defined specific exception types to distinguish between transient and permanent errors:

```python
class RateLimitError(Exception):
    """Raised when API rate limit is exceeded"""
    pass

class RequestError(Exception):
    """Raised for transient HTTP errors (5xx, timeout, etc.)"""
    pass

class BadStatusCodeError(Exception):
    """Raised for permanent HTTP errors (4xx)"""
    pass

class KeywordOnlyArgumentError(Exception):
    """Raised for invalid function arguments"""
    pass
```

**Rationale**:
- **Transient errors** (`RateLimitError`, `RequestError`): Can be retried
- **Permanent errors** (`BadStatusCodeError`, `KeywordOnlyArgumentError`): Should not be retried
- **Error handling decorator**: `handle_exceptions()` wraps resource methods to catch and log errors uniformly
- **Error result type**: `MarketDataClientErrorResult` allows returning errors without raising exceptions

This separation enables:
- Intelligent retry logic that knows which exceptions to retry
- Consistent error handling across the SDK
- Better error messages and logging

### Layer 2: Intelligent Retries with Tenacity

We use the **Tenacity** library to handle retries declaratively:

```python
def get_retry_adapter(
    attempts: int,
    backoff: float,
    exceptions: list[Exception],
    logger: Logger,
    reraise: bool = False,
    min_backoff: float = 0.5,
    max_backoff: float = 5,
) -> Retrying:
    return Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(
            multiplier=backoff, 
            min=min_backoff, 
            max=max_backoff
        ),
        retry=retry_if_exception_type(*exceptions),
        reraise=reraise,
        before_sleep=before_sleep_log(logger, log_level=DEBUG),
    )
```

**Features**:
- **Exponential Backoff**: Wait increases exponentially between retries (0.5s → 5s maximum)
- **Retry if Exception Type**: Only retries for specific exceptions (transient)
- **Automatic Logging**: Records each failed attempt
- **Configurable**: Number of attempts, backoff, exceptions, etc.

### Layer 3: Proactive Service Status Checking

We implemented **APIStatusData** to query and cache service status:

```python
class APIStatusData:
    def get_api_status(
        self, 
        client: "MarketDataClient", 
        service: str
    ) -> APIStatusResult:
        # If data is stale, refresh
        if self.should_refresh:
            self.refresh(client)
        
        # Check service status
        if self.status[service_index] != APIStatusResult.ONLINE:
            return APIStatusResult.OFFLINE
        
        return APIStatusResult.ONLINE
    
    def refresh(self, client: "MarketDataClient") -> bool:
        # Call /status/ endpoint to get current status
        response = client._make_request(method="GET", url="/status/", ...)
        self.update(response.json())
        return True
```

**Features**:
- **Smart Cache**: Only refresh if `REFRESH_API_STATUS_INTERVAL` has passed
- **Rich Information**: 
  - Status (online/offline)
  - Availability (online flag)
  - Uptime last 30 and 90 days
  - Last update timestamp
- **Global Singleton**: `API_STATUS_DATA` shared across the application

### Integration

```python
# In client or resource
status = API_STATUS_DATA.get_api_status(client, "stocks")
if status == APIStatusResult.OFFLINE:
    raise ServiceUnavailableError(f"Service 'stocks' is offline")

# Automatic retries for specific exceptions
retry_adapter = get_retry_adapter(
    attempts=3,
    backoff=1.0,
    exceptions=[RateLimitError, RequestError],
    logger=self.logger
)

for attempt in retry_adapter:
    with attempt:
        response = client._make_request(...)
```

## Consequences

### Positive
- **Automatic Resilience**: Transient errors are automatically retried
- **User Experience**: Fewer apparent failures in unstable network conditions
- **Exponential Backoff**: Prevents saturating the server with aggressive retries
- **Proactive Visibility**: Client knows if a service is down before failing
- **Status Cache**: No need to consult `/status/` on every request
- **Automatic Logging**: Each failed attempt is recorded
- **Configurable**: Number of attempts, wait times, exceptions can be adjusted

### Negative
- **Additional Latency**: In case of errors, wait time is added
- **Complexity**: More code to handle retries and status
- **False Positives**: Status cache could be stale (mitigated with refresh interval)
- **No Success Guarantee**: A down service will still fail, just delayed

### Mitigations
- Users can configure the number of attempts (trade-off between resilience and latency)
- Status cache refresh interval is configurable
- All events are logged for debugging

## Alternatives Considered

### Alternative 1: No retries, fail fast
```python
# Fail immediately
response = client._make_request(...)
if response.status != 200:
    raise Exception("Request failed")
```

**Pros**: Simple, fast
**Cons**: Users experience failures that could have been avoided

### Alternative 2: Naive retries (fixed sleep)
```python
for i in range(3):
    try:
        return client._make_request(...)
    except Exception:
        time.sleep(1)  # Fixed wait
```

**Pros**: Simple
**Cons**: Doesn't scale well with multiple failures, can saturate the server

### Alternative 3: Circuit Breaker Pattern
```python
# Stop trying if too many failures in a short time
if failure_count > threshold:
    circuit.open()  # Don't allow more requests
```

**Pros**: Protects the server
**Cons**: More complex, requires additional state, can impact user experience

### Alternative 4: No proactive status checking
```python
# Only rely on retries
# Don't consult /status/ before requests
```

**Pros**: Fewer requests to the server
**Cons**: No visibility into down services, user experiences failed retries

## References

- [Tenacity Documentation](https://tenacity.readthedocs.io/)
- [Exponential Backoff Pattern](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [API Status Codes](https://en.wikipedia.org/wiki/List_of_HTTP_status_codes)
- Relevant files:
  - `src/marketdata/retry.py` - Retry configuration
  - `src/marketdata/api_status.py` - Service status checking
  - `src/marketdata/internal_settings.py` - Interval configuration
  - `src/marketdata/exceptions.py` - Custom exceptions and error handling
  - `src/marketdata/client.py` - Response validation and status code handling
