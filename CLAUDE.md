# CLAUDE.md

## Project Overview

This is `marketdata-sdk-py`, the official Python SDK for the Market Data API. It provides access to real-time and historical stock prices, options data, mutual funds, and market status.

## Development Setup

```bash
# Install dependencies (requires uv)
uv sync --group dev

# Install package in editable mode
uv pip install -e .
```

## Running Tests

```bash
# Run all tests with coverage
uv run pytest -n 4 --cov="marketdata"
```

## Code Formatting

```bash
# Check formatting
uv run black . --check
uv run isort . --profile black --check-only

# Fix formatting
uv run black .
uv run isort . --profile black
```

## Project Structure

- `src/marketdata/` - Main SDK source code
  - `client.py` - Main SDK client
  - `resources/` - API resource modules (stocks, options, funds, markets)
  - `exceptions.py` - Custom exceptions
  - `retry.py` - Retry logic
  - `settings.py` - Configuration/settings
- `tests/` - Test suite (pytest with respx for HTTP mocking)
- `docs/` - Documentation
- `examples/` - Example scripts

## Key Conventions

- Python 3.10+ required
- Uses `httpx` for HTTP, `pydantic` for validation
- Formatting: `black` and `isort` (with black profile)
- Tests use `respx` for HTTP mocking and `freezegun` for time mocking
- All source code lives under `src/marketdata/`
