# ADR-005: Optional DataFrame Libraries (Pandas/Polars)

## Status
Accepted

## Context

The MarketData SDK needs to return data in DataFrame format (`OutputFormat.DATAFRAME`) to provide users with convenient data manipulation capabilities. However, different users have different preferences and requirements:

- **Pandas**: The most popular DataFrame library in Python, widely used and familiar to most data scientists
- **Polars**: A modern, high-performance DataFrame library with better performance characteristics and a different API

Additionally, not all users need DataFrame functionality:
- Some users only work with JSON or internal objects
- Installing heavy dependencies like pandas/polars increases installation time and package size
- Users may have existing projects with one library or the other already installed

Without optional dependencies:
- All users would be forced to install pandas/polars even if they don't use DataFrames
- Users couldn't choose their preferred DataFrame library
- Package size and installation time would be unnecessarily large
- Type hints would be complex (need to handle both pandas and polars types)

## Decision

We implemented an **optional dependency system with automatic handler detection** using a priority-based approach:

### 1. Optional Dependencies in pyproject.toml

```toml
[project.optional-dependencies]
pandas = [
    "pandas>=2.3.3",
]

polars = [
    "polars-lts-cpu>=1.33.1",
]
```

**Rationale**:
- **Separate optional groups**: Users can install `pandas` or `polars` independently
- **No default requirement**: Neither library is required for core SDK functionality
- **Version constraints**: Ensures compatibility with minimum required versions

### 2. Handler Priority System

We defined a priority order for DataFrame handlers:

```python
# In internal_settings.py
DATAFRAME_HANDLERS_PRIORITY = ["pandas", "polars"]
```

**Rationale**:
- **Pandas first**: Most widely used, better compatibility with existing codebases
- **Polars fallback**: Used if pandas is not available
- **Configurable**: Priority can be adjusted if needed

### 3. Lazy Import and Handler Detection

Handlers are imported lazily only when needed, with graceful fallback:

```python
# In output_handlers/__init__.py
@lru_cache(maxsize=1)
def _try_get_handler(handler: str) -> BaseOutputHandler:
    try:
        if handler == "pandas":
            from marketdata.output_handlers.pandas import PandasOutputHandler
            return PandasOutputHandler
        elif handler == "polars":
            from marketdata.output_handlers.polars import PolarsOutputHandler
            return PolarsOutputHandler
        else:
            raise ValueError(f"Invalid dataframe output handler: {handler}")
    except Exception as e:
        pass  # Library not installed
    return None

def get_dataframe_output_handler() -> BaseOutputHandler:
    for handler in DATAFRAME_HANDLERS_PRIORITY:
        handler_class = _try_get_handler(handler)
        if handler_class is not None:
            return handler_class
    raise ValueError("No dataframe output handler found")
```

**Rationale**:
- **Lazy imports**: Libraries are only imported when `OutputFormat.DATAFRAME` is requested
- **Exception handling**: Import errors are caught gracefully (library not installed)
- **Priority-based selection**: First available handler in priority order is used
- **Clear error message**: Users get a helpful error if no DataFrame library is installed
- **Caching**: `@lru_cache` ensures handler detection only happens once

### 4. Handler Abstraction

Both handlers implement a common interface:

```python
# In output_handlers/base.py
class BaseOutputHandler(ABC):
    def __init__(self, data: list[dict] | dict):
        self.data = data

    @abstractmethod
    def get_result(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement this method")
```

**Implementation**:
- **PandasOutputHandler**: Returns `pd.DataFrame` with pandas-specific features (index setting, column dropping)
- **PolarsOutputHandler**: Returns `pl.DataFrame` with polars-specific features (strict mode, Series handling)

**Rationale**:
- **Polymorphism**: Same interface, different implementations
- **Library-specific optimizations**: Each handler can leverage library-specific features
- **Consistent usage**: Resources use handlers the same way regardless of underlying library

### 5. Type Hints Strategy

Function return types use union types without explicitly specifying pandas/polars:

```python
def quotes(...) -> (
    list[StockQuote]
    | StockQuotesHumanReadable
    | dict
    | str
    | MarketDataClientErrorResult
):
    # ...
    if user_universal_params.output_format == OutputFormat.DATAFRAME:
        handler = get_dataframe_output_handler()
        return handler(data).get_result(...)  # Returns pd.DataFrame or pl.DataFrame
```

**Rationale**:
- **Runtime determination**: The actual type (pandas or polars) is determined at runtime
- **Type checker flexibility**: Union types allow both types without explicit imports
- **Documentation clarity**: Users understand they get "a DataFrame" without needing to know which library
- **Avoids conditional imports**: No need for `TYPE_CHECKING` blocks with pandas/polars imports

### 6. Usage in Resources

Resources use the handler system transparently:

```python
# In any resource method
if user_universal_params.output_format == OutputFormat.DATAFRAME:
    data = response.json()
    handler = get_dataframe_output_handler()
    return handler(data).get_result(index_columns=["symbol"])
```

**Rationale**:
- **Consistent pattern**: All resources use the same handler selection logic
- **No library-specific code**: Resources don't need to know which library is being used
- **Flexible parameters**: Handlers can accept library-specific parameters (e.g., `index_columns` for pandas)

## Consequences

### Positive
- **User choice**: Users can install their preferred DataFrame library
- **Smaller footprint**: Core SDK doesn't require heavy dependencies
- **Flexibility**: Users can install both libraries and the SDK will use pandas (priority)
- **Graceful degradation**: Clear error message if no DataFrame library is installed
- **Performance**: Users can choose polars for better performance if needed
- **Backward compatibility**: Existing pandas users continue to work
- **Future-proof**: Easy to add new DataFrame libraries (e.g., Dask, Modin)

### Negative
- **Runtime type uncertainty**: Type checkers can't determine exact DataFrame type
- **Documentation complexity**: Need to document that return type depends on installed libraries
- **Testing complexity**: Need to test with both libraries (or skip tests if not installed)
- **User confusion**: Users might not understand which library is being used
- **No explicit control**: Users can't explicitly choose polars if pandas is also installed

### Mitigations
- Clear documentation explaining the priority system
- Error messages guide users to install a DataFrame library
- Type hints use union types to accommodate both libraries
- Tests check for library availability before running DataFrame tests
- README explains optional dependencies and installation instructions

## Alternatives Considered

### Alternative 1: Require pandas as a core dependency
```python
# In pyproject.toml
dependencies = [
    "pandas>=2.3.3",
    # ...
]
```

**Pros**: Simpler implementation, guaranteed DataFrame support, explicit types
**Cons**: Forces all users to install pandas, larger package size, no choice for users

### Alternative 2: Explicit library parameter
```python
def quotes(..., dataframe_library: Literal["pandas", "polars"] = "pandas"):
    if dataframe_library == "pandas":
        return pd.DataFrame(...)
    elif dataframe_library == "polars":
        return pl.DataFrame(...)
```

**Pros**: User control, explicit types, clear intent
**Cons**: More complex API, users must know which library they want, harder to use

### Alternative 3: Separate methods per library
```python
def quotes_pandas(...) -> pd.DataFrame:
    # ...

def quotes_polars(...) -> pl.DataFrame:
    # ...
```

**Pros**: Explicit types, clear separation
**Cons**: API duplication, more methods to maintain, confusing for users

### Alternative 4: Plugin system
```python
# Users register their own DataFrame handlers
client.register_dataframe_handler("custom", CustomHandler)
```

**Pros**: Maximum flexibility, extensible
**Cons**: Over-engineered for current needs, more complex implementation

### Alternative 5: Type hints with TYPE_CHECKING
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl

def quotes(...) -> pd.DataFrame | pl.DataFrame:
    # ...
```

**Pros**: Better type checking, explicit types
**Cons**: Still requires both libraries for type checking, doesn't solve runtime uncertainty

## References

- [Python Optional Dependencies](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#installing-optional-dependencies)
- [Pandas Documentation](https://pandas.pydata.org/)
- [Polars Documentation](https://www.pola.rs/)
- Relevant files:
  - `pyproject.toml` - Optional dependencies configuration
  - `src/marketdata/internal_settings.py` - Handler priority configuration
  - `src/marketdata/output_handlers/__init__.py` - Handler detection logic
  - `src/marketdata/output_handlers/base.py` - Base handler interface
  - `src/marketdata/output_handlers/pandas.py` - Pandas implementation
  - `src/marketdata/output_handlers/polars.py` - Polars implementation
  - `src/marketdata/resources/**/*.py` - Resource methods using handlers

