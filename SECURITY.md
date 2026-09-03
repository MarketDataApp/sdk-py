# Security Policy

## Reporting a Vulnerability

**This is a public repository. Do not open a public GitHub issue for a security
vulnerability** — that discloses it to everyone before a fix is available.

Instead, report privately through GitHub's **Private Vulnerability Reporting**:

1. Go to the **Security** tab of this repository.
2. Click **Report a vulnerability**.
3. Describe the problem, including steps to reproduce, affected version(s), and
   the impact.

We will acknowledge the report, keep you informed as we investigate, and
coordinate the disclosure timeline and a fixed release with you. Please give us
a reasonable window to ship a fix before any public disclosure.

## Scope

This repo is the **MarketData Python SDK** — a client library published to PyPI
and pulled into consumers' applications. It runs on the consumer's machine (or
their servers), not on MarketData infrastructure. The security concerns that
matter here are therefore about how the library treats *its consumers*:

- **Credential handling** — the caller's API token must never be logged
  verbatim, leaked in exception messages, or written to disk. Tokens are
  obfuscated before logging (`obfuscate_token` in `utils.py`) and the
  `Authorization: Bearer` header is never emitted to logs. Regressions here are
  in scope.
- **Transport security** — TLS is validated by default (httpx verifies
  certificates) and the SDK exposes no skip-verify option. Anything that weakens
  this is in scope.
- **Injection into outbound requests** — request-building that lets caller input
  smuggle headers, path segments, or query parameters it shouldn't.
- **Deserialization safety** — the Pydantic-based response decoding path handling
  hostile or malformed API responses without arbitrary code execution, resource
  exhaustion, or crashes that a consumer can't defend against.
- **Supply-chain integrity of the published artifact** — the build and PyPI
  publish pipeline (`publish.yml`, which uses trusted publishing / OIDC), and the
  dependency tree of the shipped wheel and sdist.

Out of scope:

- **The MarketData API backend** itself. Report API/server vulnerabilities
  through the API's own channel, not here.
- **Third-party dependencies.** Vulnerabilities in resolved dependencies
  (`uv.lock`) are tracked by Dependabot (see `.github/dependabot.yml`); report
  them upstream. We will bump the affected dependency here once a fixed version
  exists.
- **CSV formula injection.** CSV output is intentionally byte-faithful to the
  API response: the SDK does not escape or rewrite cell values (e.g. values
  beginning with `=`, `+`, `-`, `@`). Guarding against formula execution when a
  CSV is opened in a spreadsheet application is the consuming application's
  responsibility.

## Security Fix Policy

This policy governs how security fixes are applied to this repository, including
fixes made by automated agents (e.g. Claude Code) working in the repo. It sorts
every security fix into one of two tiers.

The dividing line for a **library** is *consumer compatibility*. A fix that any
consumer can pick up by upgrading, with no source or behavior change on their
side, is low-risk. A fix that forces consumers to change their code or adapt to
changed runtime behavior is a breaking change and follows SemVer — those get the
maintainer gate.

### Tier 1 — Fix immediately (no approval needed)

Security fixes that are **API- and behavior-compatible for legitimate
consumers**. Existing callers keep working the same way after upgrading; only the
vulnerability is closed.

These may be fixed, tested, and committed right away. Every Tier 1 fix must be
called out in its commit message, in `CHANGELOG.md`, and in the summary reported
to the maintainer, so nothing ships silently.

Typical Tier 1 fixes:

- Tightening credential obfuscation, or plugging a token/secret/PII leak into
  logs or exception messages
- Fixing injection in request building (header/path/query smuggling) where valid
  caller input is unaffected
- Hardening the response-deserialization path against malformed or hostile API
  responses (bounds, resource limits, null handling)
- Correcting a logic flaw in an existing security check without changing its
  public contract
- Patching a vulnerable dependency by bumping to a compatible version — no public
  API or behavior change for consumers
- Hardening internal, non-public code paths (underscore-prefixed / internal infra:
  transport, retry, rate-limit, status-cache) that consumers cannot observe or
  depend on
- Fixing the build/publish pipeline (CI workflows, trusted publishing config)

### Tier 2 — Requires maintainer approval first

Any security fix that **breaks consumer compatibility or changes observable
runtime behavior**. These must NOT be applied unilaterally. The agent or
contributor stops, writes up the issue, the proposed fix, and the specific
consumer impact, and waits for the maintainer's approval before proceeding.

A fix is **Tier 2** if it does any of the following:

- Removes, renames, or changes the signature of any **public** class, method,
  function, or parameter (a source-incompatible change — SemVer major)
- Tightens input validation (e.g. a Pydantic input model) so that requests the
  SDK previously accepted are now rejected (could break existing callers)
- Changes a user-visible default (request/connect timeout, retry count or
  backoff, rate-limit behavior, base URL, API version, output format)
- Changes an API/response contract — the shape of the output Pydantic models,
  the exception types raised, or the `BaseMarketdataException` hierarchy /
  `MarketDataClientErrorResult` shape — that consumers depend on or match on
- Raises the minimum Python version, changes the published package name/coordinates,
  or otherwise forces a consumer to change their environment to keep using the SDK
- Adds a new required runtime dependency to the published package

### Classification rules

- **When in doubt, it's Tier 2.** If it is unclear which tier a fix falls into,
  treat it as Tier 2 and ask for approval.
- **No urgency exception.** Even for a critical, actively-exploitable
  vulnerability, a compatibility-breaking (Tier 2) fix waits for maintainer
  approval. Flag the urgency loudly, propose the fix, and wait. The maintainer is
  always the gate for changes that break consumers. (If a break is genuinely
  unavoidable to close a critical hole, that's a maintainer decision about
  cutting a major version — not an agent's.)

### Release of security fixes

Tiering governs *what* may be changed; the repo's normal release rules govern
*what ships to consumers*. A Tier 1 fix may be committed to a branch and merged
via the usual PR flow. **Publishing a release to PyPI** — creating the GitHub
release that triggers the publish pipeline (`publish.yml`) — requires explicit
maintainer confirmation, exactly like every other release. Automated agents never
cut or publish a release on their own.
