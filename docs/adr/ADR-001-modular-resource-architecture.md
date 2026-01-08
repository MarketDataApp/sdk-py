# ADR-001: Modular Resource Architecture

## Status
Accepted

## Context

The MarketData SDK needs to provide access to multiple types of market data:
- **Funds**: Candle data
- **Markets**: Market status and availability
- **Options**: Information about option contracts, prices, expirations, etc.
- **Stocks**: Stock information, prices, news, earnings, candles, etc.

Each domain has its own API endpoints, its own data types, and its own processing logic. When initiating the project, it was necessary to decide how to organize this functionality in a scalable, maintainable, and coherent way.

## Decision

We decided to implement a **Modular Resource Architecture**, where:

1. **Each domain is an independent resource**: `FundsResource`, `MarketsResource`, `OptionsResource`, `StocksResource`
2. **Resources are injected into the main client**: The `MarketDataClient` exposes each resource as a property
3. **Each resource is responsible for its own methods and endpoints**: 
   - `client.funds.candles()`
   - `client.markets.status()`
   - `client.options.chain()`
   - `client.stocks.quotes()`

### Implementation

```python
# In client.py
class MarketDataClient:
    def __init__(self, token: str = None, logger: Logger = None):
        # ... initialization ...
        self.funds = FundsResource(client=self)
        self.markets = MarketsResource(client=self)
        self.options = OptionsResource(client=self)
        self.stocks = StocksResource(client=self)

# Usage
client = MarketDataClient()
funds_data = client.funds.candles(...)
market_status = client.markets.status(...)
```

### Benefits

**Scalability**: New domains can be added as new `Resource` instances without modifying the client

**Separation of Concerns**: Each resource fully handles its own domain

**API Consistency**: The interface is consistent and predictable for users

**Code Organization**: 
- Each resource has its own directory: `src/marketdata/resources/{funds,markets,options,stocks}/`
- Within each directory, domain-specific methods

**Dependency Injection**: All resources receive a reference to the client, allowing shared state (headers, rate limits, logger, etc.)

## Consequences

### Positive
- Modular and easy to maintain code
- Each resource is independently testable
- Scalable for adding new domains
- Clear and consistent API for SDK users
- Reusable common logic (headers, retry logic, rate limits)

### Negative
- Requires all resources to inherit from a consistent `BaseResource` class
- Need to maintain synchronization between client and resources
- If resources have circular dependencies, testing can become complicated

### Mitigations
- Create a `BaseResource` class that standardizes the interface
- Use generic types to maintain flexibility
- Unit tests for each resource

## Alternatives Considered

### Alternative 1: Direct functions on the client
```python
client.get_funds_candles(...)
client.get_market_status(...)
```

**Pros**: Simpler initially
**Cons**: Client becomes monolithic, difficult to scale, lack of logical organization

### Alternative 2: Separate clients per domain
```python
funds_client = FundsClient()
markets_client = MarketsClient()
```

**Pros**: Maximum separation
**Cons**: User must manage multiple clients, duplication of authentication and header logic, difficult to maintain global rate limits

### Alternative 3: Factory pattern with lazy loading
```python
resources = ResourceFactory().create_all()
```

**Pros**: Flexibility in resource creation
**Cons**: Unnecessary complexity, less predictable initialization

## References

- [Pattern: Service Locator vs Dependency Injection](https://martinfowler.com/articles/injection.html)
- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle)
- Code structure: `src/marketdata/resources/`
- Main client: `src/marketdata/client.py`
