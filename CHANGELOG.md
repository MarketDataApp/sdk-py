# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
