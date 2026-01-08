# ADR-002: Input Validation with Pydantic

## Status
Accepted

## Context

The SDK needs to accept multiple parameters of different types for each MarketData API endpoint:
- Some parameters are mandatory, others optional
- There are constraints between parameters (e.g.: `min_price` must be less than `max_price`)
- Some parameters have default values
- Certain parameters have aliases (e.g.: `dateformat` vs `date_format`)
- Data must be transformed and validated before sending to the API

Without explicit validation, this can lead to:
- Runtime errors instead of early validation
- Inconsistency in type handling
- Implicit documentation instead of explicit
- Difficulty in generating clients from documentation

## Decision

We decided to use **Pydantic for explicit input validation**, with a hierarchical model structure:

### Type Structure

```python
# Base models with common configuration
class BaseInputType(BaseModel):
    def _validate_min_max(self, min_param: str | None, max_param: str | None) -> None:
        # Custom validation between fields
        ...

# Universal API parameters (apply to all endpoints)
class UserUniversalAPIParams(BaseInputType):
    output_format: OutputFormat = Field(default=OutputFormat.DATAFRAME, ...)
    date_format: DateFormat | None = Field(default=None, alias="dateformat", ...)
    columns: list[str] | None = Field(default=None, ...)
    add_headers: bool | None = Field(default=None, alias="headers", ...)
    use_human_readable: bool | None = Field(default=None, alias="human", ...)
    mode: Mode | None = Field(default=None, ...)
    filename: str | Path | None = Field(default=None, ...)

# Domain/endpoint-specific parameters
class StocksQuotesParams(UserUniversalAPIParams):
    symbols: list[str]  # Required
    figi: list[str] | None = None
    cusip: list[str] | None = None
    isin: list[str] | None = None
    
    @field_validator("symbols")
    def validate_symbols(cls, v):
        if not v or len(v) == 0:
            raise ValueError("symbols cannot be empty")
        return v
```

### Usage in Resources

```python
def quotes(self, params: StocksQuotesParams) -> dict | pd.DataFrame:
    # params is already validated and typed
    # Pydantic guarantees correct values
    url = "/quotes"
    response = self.client._make_request(
        method="GET",
        url=url,
        params=params.model_dump(by_alias=True, exclude_none=True)
    )
    return self._parse_response(response, params)
```

### Benefits

**Early Validation**: Errors are detected before making the HTTP request

**Self-Documentation**: Types are explicit and readable

**Type Conversion**: Pydantic automatically converts types (e.g.: string to Path, string to enum)

**Parameter Aliases**: Support for alternative parameter names (e.g.: API uses `dateformat`, code uses `date_format`)

**Custom Validation**: Ability to use custom validators for complex logic

**Type Hints**: Better IDE experience with autocompletion

**Automatic Documentation**: Facilitates generating documentation and OpenAPI specs in the future

## Consequences

### Positive
- Errors validated before making API requests
- Clear and autocomplete-friendly interface in IDEs
- More reliable and maintainable code
- Parameters explicitly documented
- Easy to extend with new validations

### Negative
- Overhead of Pydantic model instantiation (minimal but present)
- Learning curve for developers unfamiliar with Pydantic
- Initial verbosity in model definitions
- Possible over-engineering if validation is not complex

### Mitigations
- Benchmarks would show the overhead is negligible for most cases
- Clear documentation of Pydantic patterns
- Automation of model generation if possible

## Alternatives Considered

### Alternative 1: Dictionaries without validation
```python
def quotes(self, symbols: list[str], **kwargs):
    params = {"symbols": symbols, **kwargs}
    # No validation, no types
```

**Pros**: Less code, more flexible
**Cons**: No runtime validation, no type hints, implicit documentation, server errors

### Alternative 2: Native dataclasses
```python
@dataclass
class StocksQuotesParams:
    symbols: list[str]
    figi: list[str] | None = None
```

**Pros**: Lighter than Pydantic
**Cons**: No automatic validation, no type conversion, no aliases, manual documentation

### Alternative 3: JSON Schema with external validators
```python
schema = {
    "symbols": {"type": "array", "items": {"type": "string"}},
    ...
}
validate(params, schema)
```

**Pros**: Framework agnostic
**Cons**: More verbose, less integrated with Python, separate documentation

## References

- [Pydantic v2 Documentation](https://docs.pydantic.dev/)
- [BaseModel Configuration](https://docs.pydantic.dev/latest/concepts/models/)
- [Field Validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [Aliases](https://docs.pydantic.dev/latest/concepts/fields/#field-aliases)
- Relevant files: 
  - `src/marketdata/input_types/base.py`
  - `src/marketdata/input_types/{funds,markets,options,stocks}.py`
