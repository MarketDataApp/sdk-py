@include default

# SDK pull request rules

These rules apply to every Market Data SDK. The acceptance criteria they build
on are the SDK requirements document at
https://www.marketdata.app/docs/internal/sdk-requirements/. Where that document
and this file disagree, that document wins. Where this file and a general
review rule disagree, this file wins.

## 1. The version bump is a calculation, not an opinion

Two different questions get called "breaking". Keep them apart.

1. **Is the API change breaking?** One answer for every SDK, taken from the API
   schema diff: a parameter removed, a type changed, a default changed. It is
   decided upstream in the `api` repository, and it is not yours to decide.
2. **Does this pull request break THIS SDK's public surface?** A separate answer
   for each SDK. This is the question you answer, and it decides the bump.

The two answers are independent. An API change that is purely additive can
still break an SDK: when `dte` used to accept one value and now accepts a
range, a Java `dte(String)` has to become `dte(DteFilter)` and every caller
breaks, while a dynamically typed Python signature may not change at all. A
breaking API change can also need no SDK change at all.

**Do not form an opinion. Compare.**

Build one row for every public symbol the diff touches:

| symbol | before | after | breaking |
|--------|--------|-------|----------|

Read "before" from the `-` lines of the diff and from the base ref; read
"after" from the `+` lines. Then apply this test, without judgement:

- a public symbol that disappeared or was renamed: **breaking**
- a parameter removed, renamed, reordered, or made required: **breaking**
- a parameter type or a return type that changed: **breaking**
- a default value that changed: **breaking**
- the error type a call raises, throws or returns, changed: **breaking**
- a new public symbol, a new optional parameter, a widened accepted type:
  **not breaking**

Put the table in `evidence`. A breaking verdict with no table is an opinion,
and opinions are what this rule exists to remove: an accidental major release
is the failure it prevents.

State the result in `summary`, in this form:

`Version impact: major (1.3.0 -> 2.0.0)`, or `minor`, or `patch`, or `none`.

## 2. The bump arrives with the pull request

- a non-breaking change takes the next minor: 2.5 becomes 2.6
- a breaking change takes the next major: 2.5 becomes 3.0
- the decision belongs to each SDK on its own. The same API change can be a
  major here and a minor in the SDK next door.

A pull request that breaks the public surface carries its major bump with it.
The bump arrives as three things in the same pull request. A breaking change
that is missing any of them is `blocking`:

1. **A `CHANGELOG.md` entry under `## [Unreleased]`**, under a heading that
   names it as breaking: `### Removed (BREAKING)`, `### Changed (BREAKING)`.
   The release workflow extracts the release notes from this file and matches
   the `## [X.Y.Z]` heading exactly, so an entry that is absent here never
   reaches the release notes.
2. **A migration line** on every removal and every changed signature: the
   concrete replacement call, and every difference a caller will notice. The
   shape of the answer, a dropped column, a parameter that now has to be
   passed.
3. **The version impact, stated in the pull request description**: the word
   `major` and the two numbers. If the description claims a smaller bump than
   your table computes, that is a blocking finding, and your table is the
   evidence.

Do not ask the author to edit the version in the package metadata. The version
comes from that metadata, and the `tag-and-release` workflow promotes
`## [Unreleased]` and sets the number. The pull request's job is to make the
number unarguable, not to write it.

## 3. What needs no bump

Say this plainly when it applies, and do not ask for a CHANGELOG entry that the
change does not need:

- tests, test fixtures, CI configuration, lint configuration
- comments, docstring wording, formatting
- internal refactoring behind an unchanged public surface

A pull request that only adds tests needs no release. Tests that *find* a bug
do, and the fix carries its own entry.

## 4. The SDK stays aligned with the API

An API improvement that never reaches the SDKs is the failure this rule
prevents. The SDKs and the API stay aligned at all times.

- A pull request that adds support for an API capability covers the whole
  capability: every parameter and every accepted value the API documents, not
  the subset the author needed. Partial coverage is a finding, and you name
  exactly what is missing.
- The canonical REST documentation is authoritative for paths, parameters and
  response shapes. When the SDK and the REST documentation disagree, the SDK is
  wrong.
- Every capability needs a first-class method: `stocks` needs `prices`,
  `quotes`, `candles`, `earnings` and `news`; `options` needs `chain`,
  `expirations`, `quotes` and `lookup`; `funds` needs `candles`; `markets`
  needs `status`; `utilities` needs `status`, `headers` and `user`. Naming is
  idiomatic for the language.

## 5. A defect here is probably a defect in the others

These SDKs are six implementations of one contract, and defects travel between
them. The candle chunking defect is the example: the API treats `to=` as
inclusive, the SDKs assumed it was exclusive, and the boundary day came back
twice. It was present in four of the five SDKs.

When a pull request fixes a defect in logic that every SDK implements, say in
`summary` whether the same defect can exist in the sibling SDKs, and name them.
The logic this covers:

- date-range splitting and chunk merging
- pagination and batch fan-out
- CSV assembly, and the header row of a merged body
- response header parsing and rate-limit accounting
- no-data detection and the empty answer placeholder
- money parsing and decimal precision
- date and time normalisation

Report this as `should_fix`, never as `blocking`. The fix in front of you is
still correct. The purpose is that somebody opens the sibling issues.

## 6. Tests

- Unit tests mock every HTTP call. A new behaviour needs a test that fails
  without the change.
- **Every endpoint needs at least one integration test that calls the live
  API.** A mock proves only that the SDK parses the response the author
  expected, and that is the assumption that goes stale when the API changes. A
  pull request that adds or changes an endpoint method with no live test is a
  finding.
- An integration suite that skips when the token is absent reports success
  while it tests nothing. A change that makes a missing token skip rather than
  fail is `blocking`.
- An integration test asserts on the shape of the decoded answer: that the
  fields the SDK models arrived, and that they carry usable values. A test that
  checks only the status code passes against an endpoint that has silently
  started to answer with an empty body.
- Coverage is 100%. A new branch that nothing reaches is a finding, and so is a
  new branch with no test. Every coverage-ignore carries a comment that says
  why.

## 7. Documentation in the same pull request

A new public method, a changed parameter, a changed default and a changed
return type each need, in the same pull request:

- the docstring or the doc comment on the public method
- the resource page under `docs/`
- the README, when the method list or the quick start changes
- the `CHANGELOG.md` entry

## The public surface of this SDK

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

## sdk-py house rules

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

## Tests

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
