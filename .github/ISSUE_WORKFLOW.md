# Issue Workflow

This document defines the process for triaging and resolving bug reports in
`MarketDataApp/sdk-py`. It is written to be followed by a maintainer, human or automated.

Companion document: [BUG_FINDING.md](./BUG_FINDING.md) finds bugs proactively. This
document processes bugs that users report.

## Overview

```
Verify Permissions → New Issue → Validate → [Valid]      → Reproduce → Accept → Fix → Close
                                          → [Needs Info] → Request Info → Wait 7 days → Close
                                          → [Not a Bug]  → Explain → Close
```

---

## Step 0: Verify permissions

Before processing issues, confirm you can manage them.

```bash
gh api repos/MarketDataApp/sdk-py/collaborators/$(gh api user --jq '.login')/permission --jq '.permission'
```

| Result | Meaning | Action |
|---|---|---|
| `admin`, `maintain`, `write`, `triage` | Sufficient permission | Go to Step 1 |
| `read` | Read-only access | Stop. Ask a maintainer to elevate your access |
| Error: `404 Not Found` | Not a collaborator | Stop. You cannot manage issues |
| Error: `401 Unauthorized` | Not authenticated | Run `gh auth login` first |

Quick check — exits 0 when you can manage issues:

```bash
gh api repos/MarketDataApp/sdk-py/collaborators/$(gh api user --jq '.login')/permission --jq '.permission' \
  | grep -qE '^(admin|maintain|write|triage)$'
```

---

## Step 1: Validate the bug report

Run this checklist against every new report. The fields map directly to
[`ISSUE_TEMPLATE/bug.yml`](./ISSUE_TEMPLATE/bug.yml).

| # | Criterion | How to check | Pass | Fail |
|---|---|---|---|---|
| 1 | **API docs verified** | "API documentation verification" checkboxes | Both checked | Either unchecked |
| 2 | **Has reproduction code** | "Reproduction code" field | A real Python code block | Empty, pseudocode, or prose only |
| 3 | **Code is complete** | Look for client construction | Has `from marketdata import ...` and `MarketDataClient(...)` | Missing imports or client setup |
| 4 | **Names the resource and method** | "SDK resource" + "Method" | Both present, e.g. `stocks` / `stocks.candles` | Empty or vague |
| 5 | **Specifies SDK version** | "SDK version" | A concrete version, e.g. `1.3.0` | Empty or "latest" |
| 6 | **Specifies Python version** | "Python version" | A concrete version, e.g. `3.12.7` | Empty or vague, e.g. "3.x" |
| 7 | **Describes expected behavior** | "Expected behavior" | A clear statement | Empty or unclear |
| 8 | **Describes actual behavior** | "Actual behavior" | A clear statement, ideally with the traceback or the returned object | Empty or unclear |

**Bonus signal, not required:** the "Support info" field. When a call raised, the
exception's `support_info` carries `request_id`, `request_url`, `status_code`,
`timestamp`, `message` and `exception_type` (the request fields read `N/A` / `0` for
failures that never reached the API). That identifies the exact upstream request and
usually settles whether the fault is in the SDK or the API. Ask for it whenever an
exception is involved and the block is missing.

**Check the output format first.** A large share of "wrong data" reports are really "wrong
output format". The default is `OutputFormat.DATAFRAME`, and it behaves differently from
`OutputFormat.INTERNAL` on purpose: DATAFRAME drops the `s` column, sets an index, and
converts timestamp columns, while INTERNAL returns dataclass-style output objects.
Establish which one the reporter used before assuming the decoder is wrong.

**Check which exception they caught.** Every resource method raises on failure, and every
SDK exception derives from `BaseMarketdataException`. A report of the form "my
`except RequestError` never fired" is usually a different class being raised (a 400 is a
`BadStatusCodeError`, a bad parameter value is a Pydantic `ValidationError`). Ask for the
full traceback and the `support_info` block before triaging it as a bug.

### Decision

- **All 8 pass** → Step 2 (Reproduce)
- **Any fail** → Step 4 (Request more information)

---

## Step 2: Reproduce the bug

1. Create a scratch virtualenv, or add a test under `src/tests/`.

   ```bash
   cd "$(mktemp -d)"
   python -m venv .venv && . .venv/bin/activate
   pip install "marketdata-sdk-py==X.Y.Z"          # the reported version
   pip install "marketdata-sdk-py[pandas]==X.Y.Z"  # if the report uses DATAFRAME output
   ```

2. Use the reported SDK version. `==X.Y.Z` pins it exactly; do not test against `main` and
   assume it matches.
3. Use the reported Python version if you can. CI covers 3.10, 3.11 and 3.12, and the
   minimum is 3.10.
4. Clear the environment first. `MARKETDATA_*` variables and a `.env` file in the working
   directory both feed `MarketDataSettings`, and either can change the result:

   ```bash
   env | grep MARKETDATA_
   ```

5. Run it and compare against the reported "Actual behavior".

### Decision

| Outcome | Next step |
|---|---|
| **Reproduces** — output matches the report | Step 3A (Accept) |
| **Does not reproduce** — the code works | Step 3B (Cannot reproduce) |
| **Different error** — fails, but not as reported | Step 4 (Request more information) |
| **API error, not SDK error** — the API itself returns the error | Step 3C (Not an SDK bug) |
| **Expected API behavior** — the SDK faithfully returns what the API sent | Step 3C (Not an SDK bug) |
| **User error** — the reproduction code is wrong | Step 3C (Not an SDK bug) |

> **Reproduces on one Python version only?** That is a real bug, not a non-repro. CI runs
> 3.10, 3.11 and 3.12 for exactly this reason. Record which version is affected and go to
> Step 3A.

> **Reproduces with pandas but not polars (or the reverse)?** Also a real bug. The two
> output handlers are separate implementations (`output_handlers/pandas.py` and
> `output_handlers/polars.py`) and pandas wins whenever both are installed, so a
> polars-only defect is easy to miss. Record which handler you used.

---

## Step 3A: Accept as a bug

1. Add the label `accepted`.
2. Comment with the template below.
3. Go to Step 5.

```markdown
Thanks for the detailed report. I've reproduced this.

**Reproduction confirmed:**
- SDK version: [version]
- Python version: [version]
- Output format: [DATAFRAME / INTERNAL / JSON / CSV]
- DataFrame library: [pandas / polars / n/a]
- Behavior: [what you observed]

Working on a fix.
```

---

## Step 3B: Cannot reproduce

1. Add the label `needs-info`.
2. Comment with the template below.

```markdown
I wasn't able to reproduce this with the information provided.

**My environment:**
- SDK version: [version]
- Python version: [version]
- Output format: [format]
- DataFrame library: [pandas / polars / neither]
- OS: [os]

**What I observed:**
[What actually happened — worked correctly, different output, etc.]

Could you provide:
- [ ] The `support_info` block: catch the exception and `print(e.support_info)` — it contains the request id and URL we need, and never includes your API token
- [ ] Any `MARKETDATA_*` environment variables or `.env` file in play (`env | grep MARKETDATA_`), and any arguments you pass to `MarketDataClient(...)`
- [ ] The complete traceback, if an exception escaped the SDK
- [ ] The output of `pip show marketdata-sdk-py httpx pydantic pandas polars-lts-cpu` and `python --version`

I'll keep this open for 7 days for additional information.
```

---

## Step 3C: Not an SDK bug

1. Add the label `wontfix`.
2. Comment with the applicable template.
3. Close the issue.

### API issue, not the SDK

```markdown
Thanks for the report. After investigation this is behavior of the Market Data API itself rather than the Python SDK.

**What's happening:**
[Explain the API behavior]

**Suggested next steps:**
- Check the [API documentation](https://www.marketdata.app/docs/api) for this endpoint
- Contact [Market Data support](https://www.marketdata.app/dashboard/) if you believe the API behavior is wrong
- Join the [Discord](https://discord.com/invite/GmdeAVRtnT) for community help

Closing as outside the SDK's scope. Please open a new issue if you find an SDK-specific problem.
```

### Expected API behavior

```markdown
Thanks for the report. After checking the [API documentation](https://www.marketdata.app/docs/api), this matches how the API is designed to work.

**What you're seeing:**
[Describe the behavior]

**Documentation reference:**
[Link or quote]

The SDK returns data exactly as the API provides it. If you believe the documentation is wrong, or the API should behave differently, please contact [Market Data support](https://www.marketdata.app/dashboard/) or join the [Discord](https://discord.com/invite/GmdeAVRtnT).

Closing as working-as-designed.
```

### User error

~~~markdown
Thanks for the report. Reviewing the reproduction code, this looks like an issue in the calling code rather than a bug in the SDK.

**The issue:**
[Explain what's wrong]

**Suggested fix:**
```python
# Corrected code
```

**Documentation reference:**
[Link if applicable]

Closing this, but reopen if you believe there is still an SDK bug. For usage help, the [Discord](https://discord.com/invite/GmdeAVRtnT) is the fastest place to ask.
~~~

### A different exception class than expected

~~~markdown
Thanks for the report. The SDK is behaving as designed here — this is the error-handling contract rather than a bug.

Resource methods raise on failure, and the class tells you what happened: `RequestError` for retryable server errors (above 500, raised after the retries), `BadStatusCodeError` for every other non-success status, `RateLimitError` when your credits are exhausted, and the validation classes before any request is made. All of them derive from `BaseMarketdataException`:

```python
from marketdata import BaseMarketdataException, MarketDataClient

client = MarketDataClient()
try:
    result = client.stocks.prices("AAPL")
except BaseMarketdataException as e:
    print(e.exception_type)   # the class that was raised
    print(e.support_info)     # request id, URL, status code, timestamp
```

Closing, but please reopen if the exception itself is wrong (missing support context, a class that does not describe what happened, and so on) — that would be a real bug.
~~~

---

## Step 4: Request more information

1. Add the label `needs-info`.
2. Comment, keeping only the items you actually need.
3. Check back in 7 days.

```markdown
Thanks for the report. To investigate I need some additional information:

- [ ] **API documentation verification**: Please confirm you've checked the [API documentation](https://www.marketdata.app/docs/api) and that the behavior differs from what it describes
- [ ] **Complete reproduction code**: A self-contained Python snippet including the imports and `MarketDataClient(...)` construction
- [ ] **Support info**: If the call raised, catch the exception and paste `e.support_info` — it carries the request id, URL, status code and timestamp, and never includes your API token
- [ ] **SDK version**: The output of `pip show marketdata-sdk-py`
- [ ] **Python version**: The output of `python --version`
- [ ] **Output format**: The `output_format` you passed (the default is `OutputFormat.DATAFRAME`)
- [ ] **DataFrame library**: Whether you have pandas, polars, both, or neither installed
- [ ] **Environment**: The output of `env | grep MARKETDATA_`, and whether a `.env` file is present
- [ ] **Expected behavior**: What did you expect?
- [ ] **Actual behavior**: What happened? Include the full traceback if one was printed
- [ ] **Additional context**: [Specify]

I'll keep this open for 7 days. Without a response I'll close it, but you're always welcome to reopen with the details.
```

### 7-day follow-up

```markdown
Closing due to inactivity. If you can provide the requested information, feel free to reopen or open a new issue with the additional details.
```

---

## Step 5: Fix the bug

1. [ ] **Write a failing test** under `src/tests/` — one file per resource method, e.g.
       `test_stocks_candles.py` — and confirm it fails. Unit tests mock all HTTP through
       `respx`; they never reach the network. Reuse the JSON fixtures in
       `src/tests/data/` and the fixtures in `src/tests/conftest.py`.

2. [ ] **Implement the minimal fix.**

3. [ ] **Confirm the new test passes.**

       ```bash
       uv run pytest src/tests/test_stocks_candles.py -q
       ```

4. [ ] **Run the full suite with coverage:**

       ```bash
       ./test.sh                 # uv sync && uv run pytest -n 4 --cov="marketdata"
       ```

       The suite reports **100% coverage** today. Nothing enforces that — there is no
       `--cov-fail-under` and no coverage status check — so read the number rather than
       trusting the build to fail.

5. [ ] **Check formatting.** `./lint.sh` rewrites files; the pre-commit hooks and any
       review will check them:

       ```bash
       ./lint.sh                                    # black + isort --profile black
       uv run black . --check
       uv run isort . --profile black --check-only
       ```

6. [ ] **If the fix touches an input model or a URL parameter, verify the request the SDK
       actually builds.** Pydantic field aliases are what reach the API (`from`, `to`,
       `dte`, `strikeLimit`, `minBid`, `headers`, `human`, `dateformat`, …), and a
       parameter with a wrong or missing alias is silently dropped rather than rejected.
       Assert on the URL in the test:

       ```python
       params = respx_mock.calls.last.request.url.params
       assert params["dte"] == "30"
       ```

7. [ ] **If the fix touches live-API behavior, cover it in the live suite.** The
       integration tests in `src/tests/integration/` run on every pull request (see
       `RELEASE_PROCESS.md` §7); add or adjust the test for the affected endpoint, and
       verify by hand first:

       ```bash
       MARKETDATA_TOKEN=... python -c "
       from marketdata import MarketDataClient, OutputFormat
       print(MarketDataClient().stocks.candles('AAPL', countback=5, output_format=OutputFormat.JSON))
       "
       ```

8. [ ] **Add a CHANGELOG entry** under `## [Unreleased]` in `CHANGELOG.md`. If that
       section does not exist yet, add it above the most recent released version.

9. [ ] **Commit** as `fix: description (closes #NNN)`.

10. [ ] **Open a PR** against `main`. The required checks are `test (3.10)`,
        `test (3.11)` and `test (3.12)`.

Examples:

- `fix(options): send days_to_expiration as dte so the filter is applied (closes #30)`
- `fix(stocks): keep the columns projection when decoding to a polars DataFrame (closes #67)`

---

## Step 6: Close the issue

1. GitHub auto-closes from a `closes #NNN` commit message once merged.
2. If it did not, close it by hand with a comment.

~~~markdown
Fixed in [commit or PR link].

This ships in the next release. To use it immediately, install from the repository:

```bash
pip install "git+https://github.com/MarketDataApp/sdk-py.git@main"
```
~~~

---

## Labels reference

| Label | Meaning | When to apply |
|---|---|---|
| `bug` | Default label from the template | Automatic on new issues |
| `accepted` | Validated and reproduced | After successful reproduction |
| `needs-info` | Waiting on the reporter | Report incomplete, or cannot reproduce |
| `wontfix` | Not a bug, or will not be fixed | When closing as not-a-bug |
| `dependencies` | Dependency update | Automatic on Dependabot PRs |
| `breaking-change` | Breaks backward compatibility | On a fix that needs a major version bump |

All of these exist on the repository. Do not invent new ones mid-triage — a documented
step that applies a non-existent label fails on execution.

---

## CLI reference

```bash
# Labels
gh issue edit NUMBER --add-label "accepted"
gh issue edit NUMBER --add-label "needs-info"
gh issue edit NUMBER --remove-label "bug"

# State
gh issue close NUMBER
gh issue reopen NUMBER

# Comment and inspect
gh issue comment NUMBER --body "Comment text here"
gh issue view NUMBER

# Lists
gh issue list --label "bug"
gh issue list --label "needs-info"
```

---

## Examples

### Example A: valid bug report

**Issue #42** — resource `options`, method `options.chain`, complete reproduction code
with imports and `MarketDataClient(token=...)`, expected "the `days_to_expiration` filter
narrows the chain", actual "the full chain comes back", SDK `1.2.0`, Python `3.12.7`.

**Action:** passes all criteria → reproduce → accept and fix. (This is issue #30's shape:
the parameter was being dropped because its alias never reached the query string.)

---

### Example B: incomplete report

**Issue #43** — resource `stocks`, method `stocks.prices`, reproduction code reads "I
called prices and it broke", expected "it should work", actual "it doesn't work", SDK
version empty, Python version "3.x".

**Action:** fails criteria 2, 3, 5, 6, 7, 8 → request more information, naming each
missing item.

---

### Example C: not a bug (API behavior)

**Issue #44** — `stocks` / `stocks.quotes`, complete code, expected "should return the
after-hours price", actual "returns the regular session price".

**Investigation:** the API returns regular-session prices unless `extended=True` is
passed.

**Action:** close as "Not an SDK bug" with a pointer to the API documentation and the
`extended` parameter.

---

### Example D: expected API behavior

**Issue #45** — `stocks` / `stocks.earnings`, complete code, expected "percentages like
`5.2` for 5.2%", actual "returns `0.052`", both docs checkboxes checked.

**Investigation:** the API documents percentage fields as decimals (`0.052` = 5.2%). The
SDK passes the response through unchanged.

**Action:** close as "Expected API behavior", quoting the documentation.

---

### Example E: "the wrong exception was raised"

**Issue #46** — `stocks` / `stocks.candles` with `from_date` after `to_date`. The reporter
wrapped the call in `try: ... except MinMaxDateValidationError:` and the handler never
fired.

**Investigation:** the call raised `MinMaxDateValidationError` before any request; the
reporter's handler was written for `ValueError`, which that class does not extend.

**Action:** close with the "A different exception class than expected" template in Step 3C.

---

### Example F: Python-version-specific failure

**Issue #47** — `options` / `options.quotes`, reproduces on Python 3.10, works on 3.12.

**Action:** this is a real bug. Accept it, and write the regression test so it runs on all
three versions — CI already executes the suite against 3.10, 3.11 and 3.12 separately.
