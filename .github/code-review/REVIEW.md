@include default

# sdk-py house rules

This is the official Python SDK for the Market Data API. It is public, it is
installed by customers as `marketdata-sdk-py`, and its acceptance criteria are
the SDK requirements document at
https://www.marketdata.app/docs/sdk/sdk-requirements/. Where this file and a
general rule disagree, this file wins.

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

## Public API surface

A new method, a renamed parameter, a changed default, a changed return type, a
removed argument and a widened or narrowed accepted type are all contract
changes, even when the code is correct. Each one needs, in the same pull
request:

- the PEP 257 docstring on the public method, through the `@docs` decorator;
- the resource page under `docs/`, and the README method list when the method
  list changes;
- a `CHANGELOG.md` entry.

The decorator stack order is fixed: `@docs`, `@handle_exceptions`,
`@api_error_handler`, `@universal_params`. A method that reorders it, or omits
one, is a finding.

Every endpoint must still work from required parameters alone. If a change
makes a caller pass configuration to get a useful answer, say so.

## Deprecation and breaking change

- A breaking change lands only on a `feat!:` commit aimed at the next major
  version. Anything else that breaks a caller is a finding.
- A removal carries a CHANGELOG migration line with the concrete replacement
  call and every difference a caller will notice: the shape of the answer, the
  number of rows, a dropped index, a parameter that now has to be passed.
- A removal also carries a test that pins the absence, so the surface cannot
  come back quietly.
- A deprecated surface that is about to be deleted does not need refactoring.
  Say that rather than asking for the cleanup.

## Tests

- A behaviour test drives the public client with `respx`, through
  `client.<resource>.<method>`. A test that only builds a model by hand does
  not cover the API path, and saying so is a finding.
- A new behaviour needs a test that fails without the change.
- The suite runs on Python 3.10, 3.11 and 3.12 and the project holds full
  coverage. A new branch that nothing can reach is a finding; so is a new
  branch with no test.
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
