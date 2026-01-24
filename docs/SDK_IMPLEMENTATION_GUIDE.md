# Market Data SDK Implementation Guide

This document provides language-neutral specifications for implementing Market Data SDKs. It describes the architecture, features, and behaviors that should be consistent across all SDK implementations.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Authentication](#authentication)
4. [HTTP Client](#http-client)
5. [API Endpoints](#api-endpoints)
6. [Request Flow](#request-flow)
7. [Response Handling](#response-handling)
8. [Data Models](#data-models)
9. [Error Handling](#error-handling)
10. [Rate Limiting](#rate-limiting)
11. [Retry Logic](#retry-logic)
12. [Logging](#logging)
13. [Configuration](#configuration)
14. [Output Formats](#output-formats)

---

## Overview

The Market Data SDK provides programmatic access to the Market Data API, offering financial market data including stocks, options, indices, and funds. The SDK should abstract HTTP communication, handle authentication, manage rate limits, and provide structured data models.

### Design Principles

1. **Simplicity**: Provide a clean, intuitive API that minimizes boilerplate
2. **Type Safety**: Leverage the language's type system for compile-time validation
3. **Resilience**: Handle transient failures gracefully with retry logic
4. **Observability**: Provide comprehensive logging for debugging
5. **Flexibility**: Support multiple output formats and configuration options
6. **Consistency**: Maintain consistent behavior across all SDK implementations

---

## Architecture

### Component Structure

```
SDK
├── Client (Main entry point)
│   ├── Authentication
│   ├── HTTP Client
│   ├── Rate Limit Tracker
│   └── Logger
│
├── Resources (API endpoint groups)
│   ├── Stocks
│   ├── Options
│   ├── Markets
│   ├── Funds
│   └── Utilities
│
├── Input Types (Request parameter schemas)
│   ├── Universal Parameters
│   └── Resource-Specific Parameters
│
├── Output Types (Response data models)
│   └── Typed models for each endpoint
│
├── Output Handlers (Format converters)
│   ├── JSON
│   ├── DataFrame (if applicable)
│   ├── CSV
│   └── Native Objects
│
├── Error Handling
│   ├── Custom Exceptions
│   └── Error Result Types
│
└── Configuration
    └── Settings Management
```

### Client Pattern

The SDK should use a client-based architecture where:

1. A main `MarketDataClient` class serves as the entry point
2. Resources (Stocks, Options, etc.) are accessible as properties/methods on the client
3. The client manages shared state (authentication, rate limits, configuration)
4. Resources inherit client configuration but can override per-request

```
MarketDataClient
    .stocks
        .quotes()
        .candles()
        .bulkcandles()
        .earnings()
        .news()
        .prices()
    .options
        .chain()
        .quotes()
        .expirations()
        .strikes()
        .lookup()
    .markets
        .status()
    .funds
        .candles()
    .utilities
        .status()
        .headers()
```

---

## Authentication

### Token-Based Authentication

The API uses Bearer token authentication via the `Authorization` header.

#### Token Sources (Priority Order)

1. **Direct Parameter**: Token passed directly to client constructor
2. **Environment Variable**: `MARKETDATA_TOKEN`
3. **Demo Mode**: No token (limited functionality)

#### Header Format

```
Authorization: Bearer {token}
```

#### User-Agent Header

SDKs must include a User-Agent header following RFC 7231:

```
User-Agent: marketdata-sdk-{language}/{version}
```

Examples:
- `marketdata-sdk-py/1.1.0`
- `marketdata-sdk-js/2.0.0`
- `marketdata-sdk-go/1.0.0`

#### Demo Mode

When no token is provided:
- Omit the `Authorization` header
- Log a warning about demo mode
- Skip rate limit checking (demo has different limits)
- Some endpoints may be restricted

---

## HTTP Client

### Base Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Base URL | `https://api.marketdata.app` | API base URL (configurable) |
| API Version | `v1` | Current API version |
| Timeout | 60 seconds | Request timeout |
| Method | GET | All endpoints use GET |

### Required Headers

```
Authorization: Bearer {token}
User-Agent: marketdata-sdk-{language}/{version}
```

### URL Construction

URLs should be constructed as:

```
{base_url}/{api_version}/{resource_path}/?{query_params}
```

Example:
```
https://api.marketdata.app/v1/stocks/candles/D/AAPL/?from=2024-01-01
```

### Query Parameter Encoding

- Boolean values: lowercase strings (`true`, `false`)
- Arrays/Lists: comma-separated values (`symbols=AAPL,GOOGL,MSFT`)
- Dates: ISO 8601 format (`2024-01-15`) or Unix timestamps
- Enums: lowercase string values

---

## API Endpoints

### Stocks Resource

#### Quotes

Retrieves delayed stock quotes for one or more symbols.

```
GET /v1/stocks/quotes/{symbol}/
GET /v1/stocks/quotes/?symbols={symbol1},{symbol2},...
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | string | Yes* | Stock symbol (URL path for single) |
| symbols | string | Yes* | Comma-separated symbols (query param for multiple) |
| 52week | boolean | No | Include 52-week high/low data |
| extended | boolean | No | Include extended hours data (default: true) |

*Use either `symbol` in path OR `symbols` as query parameter.

#### Candles

Retrieves OHLCV (Open, High, Low, Close, Volume) candlestick data.

```
GET /v1/stocks/candles/{resolution}/{symbol}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| resolution | string | Yes | Time resolution (URL path) |
| symbol | string | Yes | Stock symbol (URL path) |
| from | date | No | Start date (mutually exclusive with countback) |
| to | date | No | End date |
| countback | integer | No | Number of bars before `to` date |
| adjustsplits | boolean | No | Adjust for splits (default: true for daily) |
| extended | boolean | No | Include extended hours (default: false) |

**Resolutions:**
- Minute: `1`, `3`, `5`, `15`, `30`, `45`
- Hourly: `H`, `1H`, `2H`, `4H`
- Daily: `D`, `1D`
- Weekly: `W`
- Monthly: `M`
- Yearly: `Y`

**Note:** Intraday requests are limited to 1 year maximum date range.

#### Bulk Candles

Retrieves daily candles for multiple symbols at once.

```
GET /v1/stocks/bulkcandles/{resolution}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| resolution | string | Yes | Currently supports daily only: `D`, `1D`, `daily` |
| symbols | string | No* | Comma-separated symbols |
| snapshot | boolean | No* | Return candles for all available symbols |
| date | date | No | Candle date (default: current/most recent session) |
| adjustsplits | boolean | No | Adjust for splits (default: true) |

*Either `symbols` or `snapshot=true` is required.

#### Earnings

Retrieves earnings data for a stock.

```
GET /v1/stocks/earnings/{symbol}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | string | Yes | Stock symbol (URL path) |
| from | date | No | Earliest earnings report date |
| to | date | No | Latest earnings report date |
| countback | integer | No | Number of reports before `to` date |
| date | date | No | Specific earnings date |
| report | string | No | Report key format (e.g., `2023-Q4`) |

#### News

Retrieves financial news for a stock.

```
GET /v1/stocks/news/{symbol}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | string | Yes | Stock symbol (URL path) |
| from | date | No | Earliest news date |
| to | date | No | Latest news date |
| countback | integer | No | Number of articles before `to` date |
| date | date | No | News for specific day |

#### Prices

Retrieves real-time stock prices.

```
GET /v1/stocks/prices/{symbol}/
GET /v1/stocks/prices/?symbols={symbol1},{symbol2},...
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| symbol | string | Yes* | Stock symbol (URL path for single) |
| symbols | string | Yes* | Comma-separated symbols (query param for multiple) |
| extended | boolean | No | Include extended hours prices (default: true) |

*Use either `symbol` in path OR `symbols` as query parameter.

### Options Resource

#### Chain

Retrieves the full options chain for an underlying symbol.

```
GET /v1/options/chain/{underlyingSymbol}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| underlyingSymbol | string | Yes | Underlying ticker symbol (URL path) |

**Date & Expiration Filters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| date | date | Historical end-of-day chain from specific trading day |
| expiration | date | Limit to specific expiration (use `all` for complete chain) |
| dte | integer | Filter by days-to-expiry closest to value |
| from | date | Expiration date range start (inclusive) |
| to | date | Expiration date range end (inclusive) |
| month | integer | Filter by expiration month (1-12) |
| year | integer | Filter by expiration year |
| weekly | boolean | Include/exclude weekly expirations |
| monthly | boolean | Include/exclude standard monthly expirations |
| quarterly | boolean | Include/exclude quarterly expirations |

**Strike Filters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| strike | string | Specific strike(s) or range (e.g., `400`, `400-410`, `>400`) |
| delta | float | Strike(s) matching specific delta value(s) or range |
| strikeLimit | integer | Maximum number of strikes to return |
| range | string | Filter by moneyness: `itm`, `otm`, or `all` |

**Price/Liquidity Filters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| minBid | float | Minimum bid price |
| maxBid | float | Maximum bid price |
| minAsk | float | Minimum ask price |
| maxAsk | float | Maximum ask price |
| maxBidAskSpread | float | Maximum spread in dollars |
| maxBidAskSpreadPct | float | Maximum spread as percentage |
| minOpenInterest | integer | Minimum open interest |
| minVolume | integer | Minimum trading volume |

**Other Filters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| nonstandard | boolean | Include non-standard contracts |
| side | string | Limit to `call` or `put` |

#### Quotes

Retrieves quotes for a specific option contract.

```
GET /v1/options/quotes/{optionSymbol}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| optionSymbol | string | Yes | OCC-formatted option symbol (URL path) |
| date | date | No | Historical end-of-day quote from specific trading day |
| from | date | No | Start date for series of end-of-day quotes |
| to | date | No | End date for series of end-of-day quotes |

#### Expirations

Retrieves available expiration dates for an underlying.

```
GET /v1/options/expirations/{underlyingSymbol}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| underlyingSymbol | string | Yes | Underlying ticker symbol (URL path) |
| strike | float | No | Filter to expirations containing specific strike |
| date | date | No | Historical expirations from prior trading day |

#### Strikes

Retrieves available strike prices for an underlying.

```
GET /v1/options/strikes/{underlyingSymbol}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| underlyingSymbol | string | Yes | Underlying ticker symbol (URL path) |
| expiration | date | No | Filter to strikes for specific expiration |
| date | date | No | Historical strikes from prior trading day |

#### Lookup

Converts human-readable option description to OCC symbol format.

```
GET /v1/options/lookup/{userInput}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| userInput | string | Yes | Human-readable option description (URL path, URL-encoded) |

**Example:** `AAPL 7/28/2023 200 Call` → `AAPL230728C00200000`

### Markets Resource

#### Status

Retrieves market open/closed status.

```
GET /v1/markets/status/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| country | string | No | Two-digit ISO 3166 country code (default: US) |
| date | date | No | Specific date to check status |
| from | date | No | Date range start (inclusive) |
| to | date | No | Date range end (inclusive) |
| countback | integer | No | Number of dates before `to` date |

**Response Values:**
- `status`: Returns `open`, `closed`, or `null` (for dates beyond available data)
- Half-days are reported as `open`

### Funds Resource

#### Candles

Retrieves OHLCV data for mutual funds and ETFs.

```
GET /v1/funds/candles/{resolution}/{symbol}/
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| resolution | string | Yes | Time resolution (URL path): `D`, `W`, `M`, `Y` |
| symbol | string | Yes | Fund ticker symbol (URL path) |
| from | date | Yes* | Start date (inclusive) |
| to | date | No | End date (inclusive) |
| countback | integer | Yes* | Number of candles before `to` date |

*Either `from` or `countback` is required.

**Note:** Intraday resolutions are not available for funds. Only daily and longer resolutions are supported.

### Utilities Resource

Utility endpoints for debugging and monitoring. These endpoints do **not** require authentication and do **not** use the `/v1/` API version prefix.

#### Status

Retrieves the operational status of all Market Data services.

```
GET /status/
```

No parameters required. This endpoint is public and accessible even when the API is offline.

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| s | string | Status indicator (`ok` or `error`) |
| service | array[string] | List of monitored services |
| status | array[string] | Current state per service (`online` or `offline`) |
| online | array[boolean] | Boolean availability flags |
| uptimePct30d | array[float] | 30-day uptime percentage per service |
| uptimePct90d | array[float] | 90-day uptime percentage per service |
| updated | array[date] | Last status update timestamp per service |

**Note:** Status updates every 5 minutes.

#### Headers

Echoes back the request headers received by the API. Useful for debugging authentication and header issues.

```
GET /headers/
```

No parameters required. Returns a JSON object containing all headers from the client's request. The `Authorization` header value is partially masked for security.

---

## Request Flow

### Processing Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│ 1. METHOD INVOCATION                                          │
│    client.stocks.quotes("AAPL", extended=true)               │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. PARAMETER VALIDATION                                       │
│    - Validate required parameters                            │
│    - Apply type conversions                                  │
│    - Merge with default configuration                        │
│    - Validate parameter ranges and allowed values            │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. URL CONSTRUCTION                                           │
│    - Build path from resource and parameters                 │
│    - Encode query parameters                                 │
│    - Construct full URL with base and version               │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. RATE LIMIT CHECK                                           │
│    - Check if requests_remaining > 0                         │
│    - Raise error or block if limit exceeded                  │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. REQUEST EXECUTION                                          │
│    - Log pre-request (DEBUG level)                           │
│    - Execute HTTP GET request                                │
│    - Capture response and timing                             │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. RESPONSE VALIDATION                                        │
│    - Check HTTP status code                                  │
│    - Extract error message if applicable                     │
│    - Raise appropriate exception for errors                  │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. POST-RESPONSE PROCESSING                                   │
│    - Log response details (INFO level)                       │
│    - Update rate limit tracking from headers                 │
│    - Parse response body                                     │
└──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 8. OUTPUT FORMATTING                                          │
│    - Convert to requested output format                      │
│    - Apply timezone conversions                              │
│    - Return typed result                                     │
└──────────────────────────────────────────────────────────────┘
```

---

## Response Handling

### API Response Format

All API responses follow this JSON structure:

#### Success Response

```json
{
  "s": "ok",
  "field1": [...],
  "field2": [...],
  "updated": [...]
}
```

The `s` field indicates status:
- `ok`: Request successful, data follows
- `no_data`: Request successful, but no data matched criteria
- `error`: Request failed

#### Error Response

```json
{
  "s": "error",
  "errmsg": "Description of the error"
}
```

### Parsing Responses

API responses use a columnar format where each field is an array:

```json
{
  "s": "ok",
  "symbol": ["AAPL", "GOOGL"],
  "ask": [150.25, 2750.00],
  "bid": [150.20, 2749.50],
  "updated": [1704067200, 1704067200]
}
```

To convert to records:
1. Identify the array length (all arrays have same length)
2. Transpose to create individual records
3. Map to typed objects

```
Record 0: {symbol: "AAPL", ask: 150.25, bid: 150.20, updated: 1704067200}
Record 1: {symbol: "GOOGL", ask: 2750.00, bid: 2749.50, updated: 1704067200}
```

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Parse response |
| 203 | Success (cached) | Parse response |
| 400 | Bad Request | Raise validation error |
| 401 | Unauthorized | Raise auth error |
| 403 | Forbidden | Raise auth error |
| 404 | Not Found | Raise not found error |
| 429 | Rate Limited | Raise rate limit error |
| 5xx | Server Error | Retry with backoff |

### Response Headers

Extract these headers from every response:

| Header | Description |
|--------|-------------|
| `x-api-ratelimit-limit` | Total requests allowed |
| `x-api-ratelimit-remaining` | Requests remaining |
| `x-api-ratelimit-reset` | Unix timestamp when limit resets |
| `x-api-ratelimit-consumed` | Requests consumed this period |
| `cf-ray` | Cloudflare request ID (for debugging) |

---

## Data Models

### Common Field Types

| API Type | Description | SDK Mapping |
|----------|-------------|-------------|
| string | Text value | String |
| float | Decimal number | Float/Double |
| int | Integer | Integer |
| timestamp | Unix timestamp (seconds) | DateTime |
| date | ISO 8601 date string | Date |
| boolean | true/false | Boolean |

### Stock Quote Model

```
StockQuote:
    symbol: string          # Stock symbol
    ask: float              # Ask price
    askSize: int            # Ask size
    bid: float              # Bid price
    bidSize: int            # Bid size
    mid: float              # Mid price
    last: float             # Last trade price
    change: float           # Price change
    changepct: float        # Percent change
    volume: int             # Trading volume
    updated: datetime       # Last update time

    # Extended fields (when 52week=true):
    high52: float           # 52-week high
    low52: float            # 52-week low
```

### Stock Candle Model

```
StockCandle:
    symbol: string          # Stock symbol
    open: float             # Open price
    high: float             # High price
    low: float              # Low price
    close: float            # Close price
    volume: int             # Volume
    time: datetime          # Candle timestamp
```

### Options Chain Model

```
OptionsChain:
    optionSymbol: string[]      # Option symbols
    underlying: string[]        # Underlying symbol
    expiration: datetime[]      # Expiration dates
    side: string[]              # "call" or "put"
    strike: float[]             # Strike prices

    # Quote data:
    bid: float[]                # Bid prices
    bidSize: int[]              # Bid sizes
    ask: float[]                # Ask prices
    askSize: int[]              # Ask sizes
    last: float[]               # Last prices
    volume: int[]               # Volumes
    openInterest: int[]         # Open interest

    # Greeks:
    delta: float[]              # Delta
    gamma: float[]              # Gamma
    theta: float[]              # Theta
    vega: float[]               # Vega
    rho: float[]                # Rho

    # Derived:
    iv: float[]                 # Implied volatility
    intrinsicValue: float[]     # Intrinsic value
    extrinsicValue: float[]     # Extrinsic value
    underlyingPrice: float[]    # Underlying price

    updated: datetime[]         # Update times
```

### Options Quote Model

```
OptionsQuote:
    optionSymbol: string    # Option symbol
    ask: float              # Ask price
    askSize: int            # Ask size
    bid: float              # Bid price
    bidSize: int            # Bid size
    mid: float              # Mid price
    last: float             # Last price
    volume: int             # Volume
    openInterest: int       # Open interest
    underlyingPrice: float  # Underlying price

    # Greeks:
    iv: float               # Implied volatility
    delta: float            # Delta
    gamma: float            # Gamma
    theta: float            # Theta
    vega: float             # Vega

    updated: datetime       # Last update
```

### Market Status Model

```
MarketStatus:
    date: date              # Date
    status: string          # "open" or "closed"
```

### Earnings Model

```
Earnings:
    symbol: string          # Stock symbol
    fiscalYear: int         # Fiscal year
    fiscalQuarter: int      # Fiscal quarter
    date: date              # Report date
    reportDate: date        # Actual report date
    reportTime: string      # "bmo" (before market open), "amc" (after market close)
    currency: string        # Currency code

    # Reported values:
    reportedEPS: float      # Reported EPS
    estimatedEPS: float     # Estimated EPS
    surpriseEPS: float      # EPS surprise
    surpriseEPSpct: float   # EPS surprise percent

    # Revenue:
    reportedRevenue: float  # Reported revenue
    estimatedRevenue: float # Estimated revenue
    surpriseRevenue: float  # Revenue surprise
    surpriseRevenuePct: float   # Revenue surprise percent

    updated: datetime       # Last update
```

### Timezone Handling

- All timestamps should be converted to the configured timezone
- Default timezone: `US/Eastern`
- Timestamps from API are Unix timestamps (seconds since epoch)
- SDKs should provide utilities for timezone conversion

---

## Error Handling

### Exception Hierarchy

```
MarketDataError (Base)
├── AuthenticationError
│   └── InvalidTokenError
├── RateLimitError
├── RequestError
│   ├── BadRequestError (400)
│   ├── NotFoundError (404)
│   └── ServerError (5xx)
├── ValidationError
│   ├── InvalidParameterError
│   └── MinMaxDateValidationError
└── ResponseError
    └── InvalidResponseError
```

### Error Response Type

For languages that support sum types or result types, provide an alternative to exceptions:

```
Result<T, Error>
  - Success: Contains the response data of type T
  - Error: Contains error information

ErrorResult:
    error: Exception        # The exception that occurred
    message: string         # Human-readable error message
    code: string            # Error code (optional)
```

### Error Handling Strategy

1. **Graceful Degradation**: Catch errors and return error result types instead of throwing
2. **Logging**: Log all errors at ERROR level
3. **Retry on Transient Errors**: Server errors (5xx) should trigger retry logic
4. **Clear Messages**: Provide actionable error messages

### Validation Errors

Validate parameters before making requests:

1. **Required Parameters**: Check all required parameters are present
2. **Type Validation**: Ensure parameter types match expected types
3. **Range Validation**: Validate numeric ranges, date ranges
4. **Enum Validation**: Validate enum values against allowed options
5. **Date Range**: Ensure `from` date is before `to` date

---

## Rate Limiting

### Rate Limit Data

Track these values from response headers:

```
RateLimits:
    limit: int              # Total requests allowed per period
    remaining: int          # Requests remaining in current period
    reset: datetime         # When the limit resets
    consumed: int           # Requests consumed in current period
```

### Rate Limit Behavior

1. **Initialization**: Fetch rate limits on client initialization by calling a lightweight endpoint
2. **Per-Request Update**: Update rate limits from every response
3. **Pre-Request Check**: Before each request, verify `remaining > 0`
4. **Error on Exceeded**: Raise `RateLimitError` if limit would be exceeded

### Rate Limit Headers

```
x-api-ratelimit-limit: 50000
x-api-ratelimit-remaining: 49985
x-api-ratelimit-reset: 1704153600
x-api-ratelimit-consumed: 15
```

### Demo Mode

When no token is provided:
- Skip rate limit initialization
- Skip pre-request rate limit checks
- Demo accounts have different (limited) rate limits

---

## Retry Logic

### Retry Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Max Attempts | 3 | Maximum retry attempts |
| Min Backoff | 0.5s | Minimum wait between retries |
| Max Backoff | 5s | Maximum wait between retries |
| Backoff Multiplier | 0.5 | Exponential backoff multiplier |
| Jitter | Yes | Add random jitter to prevent thundering herd |

### Retry Conditions

Retry requests when:
- HTTP status code > 500 (server errors)
- Network timeout or connection error
- API service check indicates service is online

Do NOT retry when:
- Client errors (4xx)
- Rate limit exceeded (429)
- Authentication failed (401, 403)
- API service check indicates service is offline

### Exponential Backoff

```
wait_time = min(max_backoff, min_backoff * (multiplier ^ attempt)) + random_jitter
```

### Service Status Check

Before retrying after a `RequestError`:

1. Check API service status endpoint
2. If service is ONLINE: Proceed with retry
3. If service is OFFLINE or UNKNOWN: Raise error immediately

Service status should be cached for approximately 4.5 minutes.

---

## Logging

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed request/response data, internal state |
| INFO | Request summaries, configuration |
| WARNING | Demo mode, deprecated features |
| ERROR | Failed requests, exceptions |

### Log Points

1. **Client Initialization** (INFO):
   - Base URL, API version
   - Token presence (not the token itself!)

2. **Pre-Request** (DEBUG):
   - Full URL being requested

3. **Post-Request** (INFO):
   - HTTP method
   - Status code
   - Request duration
   - Request ID (cf-ray)
   - URL

4. **Retry Attempts** (DEBUG):
   - Retry number
   - Wait time

5. **Errors** (ERROR):
   - Exception type
   - Error message
   - Context (URL, parameters)

### Log Format

```
{timestamp} - {logger_name} - {level} - {message}
```

Example:
```
2024-01-15 10:30:45 - marketdata.client - INFO - GET 200 045ms abc123 https://api.marketdata.app/v1/stocks/quotes/?symbols=AAPL
```

### Duration Formatting

Format request duration for readability:
- < 1 second: `###ms` (e.g., `045ms`)
- < 10 seconds: `#.##s` (e.g., `2.34s`)
- >= 10 seconds: `##.#s` (e.g., `15.2s`)

---

## Configuration

### Configuration Sources

Process configuration in this priority order (highest first):

1. **Per-Request Parameters**: Override for single request
2. **Client Instance Settings**: Set on client object
3. **Environment Variables**: Read from environment
4. **Default Values**: Built-in defaults

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MARKETDATA_TOKEN` | string | (none) | API authentication token |
| `MARKETDATA_BASE_URL` | string | `https://api.marketdata.app` | API base URL |
| `MARKETDATA_API_VERSION` | string | `v1` | API version |
| `MARKETDATA_LOGGING_LEVEL` | string | `INFO` | Log level |
| `MARKETDATA_OUTPUT_FORMAT` | string | (none) | Default output format |
| `MARKETDATA_DATE_FORMAT` | string | (none) | Default date format |

### Configuration Object

```
Settings:
    token: string               # API token
    base_url: string            # API base URL
    api_version: string         # API version (v1)
    logging_level: string       # Log level

    # Universal parameters:
    output_format: OutputFormat # Default output format
    date_format: DateFormat     # Default date format
    columns: string[]           # Columns to include
    use_human_readable: bool    # Use human-readable field names
```

### Internal Constants

These values should be configurable but have sensible defaults:

| Constant | Value | Description |
|----------|-------|-------------|
| `HTTP_TIMEOUT` | 60s | Request timeout |
| `MAX_RETRY_ATTEMPTS` | 3 | Maximum retries |
| `MIN_RETRY_BACKOFF` | 0.5s | Minimum retry wait |
| `MAX_RETRY_BACKOFF` | 5s | Maximum retry wait |
| `RETRY_BACKOFF_MULTIPLIER` | 0.5 | Backoff multiplier |
| `MAX_CONCURRENT_REQUESTS` | 50 | Max parallel requests |
| `API_STATUS_CACHE_TTL` | 270s | Service status cache time |
| `VALID_STATUS_CODES` | [200, 203] | Successful status codes |

---

## Output Formats

### Supported Formats

| Format | Description |
|--------|-------------|
| `json` | Raw JSON dictionary/object |
| `internal` | Native language objects/structs |
| `dataframe` | Tabular data structure (if available) |
| `csv` | CSV file output |

### JSON Format

Return the parsed JSON response directly:

```json
{
  "s": "ok",
  "symbol": ["AAPL"],
  "ask": [150.25],
  "bid": [150.20]
}
```

### Internal/Native Format

Convert JSON to typed language objects:

```
[
  StockQuote(symbol="AAPL", ask=150.25, bid=150.20, ...)
]
```

### DataFrame Format

For languages with tabular data libraries (Pandas, Polars, DataFrames.jl):

```
| symbol | ask    | bid    | updated             |
|--------|--------|--------|---------------------|
| AAPL   | 150.25 | 150.20 | 2024-01-15 10:30:00 |
```

### CSV Format

Write response to a CSV file:

```csv
symbol,ask,bid,updated
AAPL,150.25,150.20,2024-01-15T10:30:00-05:00
```

Return the file path after writing.

### Date Formats

Support multiple date output formats:

| Format | Example | Description |
|--------|---------|-------------|
| `timestamp` | `2024-01-15T10:30:00-05:00` | ISO 8601 with timezone |
| `unix` | `1705329000` | Unix timestamp (seconds) |
| `spreadsheet` | `45306.4375` | Excel/Sheets serial number |

---

## Universal Parameters

These parameters apply to all endpoints:

| Parameter | Type | Description |
|-----------|------|-------------|
| `format` | string | Output format (json, csv) |
| `columns` | string | Comma-separated column names to include |
| `dateformat` | string | Date format (timestamp, unix, spreadsheet) |
| `human` | boolean | Use human-readable column names |

### Human-Readable Mode

When enabled, transform field names:
- `askSize` → `Ask Size`
- `changepct` → `Change Percent`
- `openInterest` → `Open Interest`

---

## Concurrency Support

### Parallel Requests

For operations that require multiple API calls (e.g., large date ranges):

1. **Split Request**: Divide into smaller chunks
2. **Execute Concurrently**: Use thread pool or async execution
3. **Merge Results**: Combine responses in order
4. **Rate Limit Awareness**: Track rate limits across parallel requests

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Max Concurrent | 50 | Maximum parallel requests |

---

## Implementation Checklist

Use this checklist when implementing an SDK:

### Core Components

- [ ] Client class with token authentication
- [ ] HTTP client with proper headers
- [ ] URL builder with query encoding
- [ ] Response parser (columnar to records)

### Resources

- [ ] Stocks: quotes, candles, bulkcandles, earnings, news, prices
- [ ] Options: chain, quotes, expirations, strikes, lookup
- [ ] Markets: status
- [ ] Funds: candles
- [ ] Utilities: status, headers

### Features

- [ ] Rate limit tracking
- [ ] Retry logic with exponential backoff
- [ ] Error handling with custom exceptions
- [ ] Logging at multiple levels
- [ ] Configuration from environment variables
- [ ] Multiple output formats

### Data Models

- [ ] Typed models for each response type
- [ ] Timezone-aware datetime handling
- [ ] Human-readable field name option

### Quality

- [ ] Comprehensive tests
- [ ] Documentation with examples
- [ ] Type definitions/annotations
- [ ] Thread safety considerations

---

## Appendix: Option Symbol Format

Option symbols follow the OCC (Options Clearing Corporation) format:

```
{underlying}{expiration}{side}{strike}
```

Example: `AAPL240119C00150000`
- Underlying: `AAPL`
- Expiration: `240119` (January 19, 2024)
- Side: `C` (Call) or `P` (Put)
- Strike: `00150000` ($150.00, padded to 8 digits with 3 decimal places)

The `lookup` endpoint can translate human-friendly formats to OCC format.

---

## Appendix: Resolution Values

| Value | Description |
|-------|-------------|
| `1` | 1 minute |
| `5` | 5 minutes |
| `15` | 15 minutes |
| `30` | 30 minutes |
| `45` | 45 minutes |
| `H` | 1 hour |
| `2H` | 2 hours |
| `4H` | 4 hours |
| `D` | Daily |
| `W` | Weekly |
| `M` | Monthly |
| `Y` | Yearly |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-01-15 | Initial specification |
| 1.1 | 2024-01-24 | Corrected endpoint URLs, added bulkcandles and utilities resources |
