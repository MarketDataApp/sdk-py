@include default
@include sdk

## 9. The public surface of this SDK

The surface is every name in `src/marketdata/` that does not start with `_`,
plus everything re-exported from `src/marketdata/__init__.py`. The package is
installed by customers as `marketdata-sdk-py`.

A signature here includes the parameter names, because callers pass them by
keyword. Renaming a parameter breaks callers even when the position is the same.

Breaking, for this SDK:

- a name removed from `__init__.py`, even when the module-level name survives
- a parameter renamed, removed, reordered, or moved from optional to required
- a type hint narrowed on a parameter, or widened on a return value
- a changed default
- a resource method that starts to raise where it used to return
  `MarketDataClientErrorResult`, or that raises a different
  `BaseMarketdataException` subclass
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
- In v1 the normal flow returns `MarketDataClientErrorResult` rather than
  raising. A change that starts raising where v1 returned a result is a
  breaking change, not a fix.
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
- The decorator stack order is fixed: `@docs`, `@handle_exceptions`,
  `@api_error_handler`, `@universal_params`. A method that reorders it, or omits
  one, is a finding.
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
- Formatting is `black` and `isort` with the black profile. Report a
  formatting problem as a nit, and only once.

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
