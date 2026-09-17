@include default
@include sdk

## 9. The public surface of this SDK

The surface is every name that a module in `src/marketdata/` defines without a
leading `_`, plus everything re-exported from `src/marketdata/__init__.py`. A
function bound onto a `*Resource` class is part of the surface as
`client.<resource>.<method>`. The package is installed by customers as
`marketdata-sdk-py`.

Apart from those re-exports, a name that a module imports is not part of its
surface. PEP 8 treats imported names as implementation details, and no module
here gives its imports an underscore: `from httpx import Response` does not add
a public `Response` to the module that imports it.

A signature here includes the parameter names, because callers pass them by
keyword. Renaming a parameter breaks callers even when the position is the same.

Breaking, for this SDK:

- a name removed from `__init__.py`, even when the module-level name survives
- a parameter renamed, removed, reordered, or moved from optional to required
- a type hint narrowed on a parameter, or widened on a return value
- a changed default
- a resource method that raises a different `BaseMarketdataException` subclass
- a field removed from a Pydantic model or a `TypedDict`, or made required
- an `Enum` member removed or its value changed

Not breaking: a new keyword argument with a default, a new model field that is
optional, a widened accepted type on a parameter.

A removal also carries a test that pins the absence, so the surface cannot come
back quietly.

# sdk-py house rules

## The four output formats must agree

Every resource method answers in `INTERNAL`, `JSON`, `CSV` or `DATAFRAME`.

- The output format must never decide whether a call raises. If one format
  raises on a body and another returns the value, that is a blocking finding.
- The format must never decide what the data means. The same body must give
  the same numbers, the same missing values and the same column names in all
  four.
- A change to one path needs a test that covers the other three, or a stated
  reason why it cannot.

## Errors are SDK exceptions

- Nothing that comes off the wire may reach the caller as a bare `ValueError`,
  `TypeError` or `KeyError`. A model or a parser that raises a built-in must be
  wrapped at the resource boundary into `ParseError` or another
  `BaseMarketdataException`.
- A model the caller builds by hand may raise a built-in. There the value came
  from the caller, not from the API.
- No resource method returns an error value. 1.x returned
  `MarketDataClientErrorResult`, and 2.0.0 drops it. A change that brings an
  error value back is a finding. The empty result for a 404 `no_data` answer,
  `{"s": "no_data"}` in JSON included, is an answer, not an error value.
- Failure metadata must name the request that raised: the URL, the status and
  the request id. A header the API sent blank reads as absent, never as an
  empty string. The token is redacted everywhere, log lines included.

## Money is a Decimal

- Money is built from the digits the API sent. A float round trip anywhere on
  the money path is a blocking finding.
- Decimal parsing must not depend on the caller's decimal context. The traps
  are thread local and finance code turns them off. Parse under a private
  context.
- A value the SDK cannot read must raise, never become `None`. A price the API
  does not have is worse than an error.

## CSV and the byte order mark

- A byte order mark at the front of a body is stripped. A mark inside a value
  is data.
- The API's empty answer placeholder must read as the empty answer with a mark
  or without one, on every accepted status.
- A fan-out chunk or a symbol with no data contributes no rows. It must not
  fail the whole call.

## The decorator stack and the docstring

- A public method's PEP 257 docstring reaches the documentation through the
  `@docs` decorator. A new or changed public method without it is a finding.
- The decorator stack is fixed. From the top, an endpoint method carries
  `@api_error_handler`, `@docs` and `@universal_params`. The `utilities`
  methods do not go through `@universal_params`, so their stack ends at
  `@docs`. Which decorators a method carries, and their order, is what is
  fixed: their arguments vary by method. A method that reorders the stack, or
  leaves out a decorator its peers carry, is a finding.
- Every endpoint must still work from required parameters alone. If a change
  makes a caller pass configuration to get a useful answer, say so.

## Deprecation

- A breaking change lands only on a `feat!:` commit aimed at the next major
  version. Anything else that breaks a caller is a finding.
- A deprecated surface that is about to be deleted does not need refactoring.
  Say that rather than asking for the cleanup.

## Tests, in this repository

- A behaviour test drives the public client with `respx`, through
  `client.<resource>.<method>`. A test that only builds a model by hand does
  not cover the API path, and saying so is a finding.
- The suite runs on Python 3.10, 3.11 and 3.12 and the project holds full
  coverage.
- Formatting and import order are `ruff`: `./lint.sh` runs it, and the lint
  workflow checks it. A formatting problem is one that `ruff check` or
  `ruff format --check` reports. Report it as a nit, and only once.

## Proof, in this repository

The standard here is higher than the default, because the pull requests here
already meet it. For a behaviour change, sufficient proof shows all of:

1. the old behaviour reproduced before the fix, through the public client, as
   output rather than as prose;
2. the new behaviour after it, from the same route;
3. the test count and the coverage number from the run.

For anything that concerns the wire — a status code, a header, a CSV body, an
endpoint that is being removed — sufficient proof also names what the live API
actually answered, and when it was measured.

Proof is `not_applicable` for documentation, comments, formatting and type
hints that change no runtime behaviour.

When proof is missing, `ask` names the single smallest run that would settle
it.

## Reviewing a stacked pull request

Several branches here are stacked on each other rather than on `main`. Review
the pull request against its own base, and do not report a change that came in
with the base as a finding of this pull request.
