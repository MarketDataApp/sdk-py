# Python SDK Release Process

This document defines the release process for `MarketDataApp/sdk-py`. The package is
[`marketdata-sdk-py`](https://pypi.org/project/marketdata-sdk-py/) on PyPI.

## 1. What "publishing" means for Python

A release is an **upload to PyPI**. `uv build` produces a wheel and an sdist from the
version declared in `pyproject.toml`, and `pypa/gh-action-pypi-publish` uploads them.

That has three consequences that shape everything below.

| | |
|---|---|
| **The version comes from `pyproject.toml`, not from the tag** | `[project] version = "X.Y.Z"` is a static string (hatchling). Nothing in CI compares it with the tag you push. Bump it in the release PR or you will publish the previous version's number again — and PyPI will reject the upload as a duplicate. |
| **Publishing is irreversible** | A `(name, version)` pair on PyPI can never be re-uploaded, even after deletion. Yanking hides a version from resolvers; it does not remove it, and anyone who pins it still gets it. |
| **There is a staging feed** | `publish.yml` uploads to [TestPyPI](https://test.pypi.org/project/marketdata-sdk-py/) first and only continues to PyPI if that succeeds. TestPyPI is a real upload with the same immutability, so a burned version number there is burned there for good. |

Both uploads use **PyPI Trusted Publishing** (OIDC). There is no API token secret in this
repository, and no `UV_PUBLISH_PASSWORD` is involved in CI. The GitHub environments
`pypi` and `testpypi` exist for this purpose and currently carry **no protection rules**,
so neither upload waits for a reviewer.

> `publish.sh` in the repository root is a **local, interactive** fallback that publishes
> with `uv publish` and your own PyPI token. It is not what CI runs and should not be the
> normal path.

## 2. Scope and versioning

The public API is covered by semantic versioning:

| Change | Version |
|---|---|
| Bug fix, no API change | `X.Y.Z` |
| New method, parameter, or output field; nothing removed or altered | `X.Y.0` |
| Anything a caller must react to | `X.0.0` |

For this SDK, "anything a caller must react to" includes: removing or renaming a public
name exported from `marketdata/__init__.py`; changing a resource method's signature or
the meaning of a keyword argument; changing the fields of an output model
(`StockCandle`, `OptionsChain`, `MarketStatus`, …); changing which exception type in
`marketdata.exceptions` is produced for a given failure; changing the shape of
`MarketDataClientErrorResult`; changing a user-visible default (`output_format`,
`max_retries`, the retry backoff, `MARKETDATA_BASE_URL`, `MARKETDATA_API_VERSION`,
`MARKETDATA_LOGGING_LEVEL`); tightening a Pydantic input model so a previously accepted
call is now rejected; or raising the minimum Python version.

Adding a new **required** runtime dependency is at least a minor bump, and is worth
avoiding: the shipped wheel currently depends only on `httpx`, `pydantic`,
`pydantic-settings`, `pytz` and `tenacity`, with pandas and polars kept as extras.

## 3. Release preparation

1. Confirm `main` is current and the **Tests** workflow is green for the commit you intend
   to release. It runs the suite on Python 3.10, 3.11 and 3.12.

2. **Bump the version.** `pyproject.toml` `[project] version` is the single source of the
   published version number. Update it to `X.Y.Z`.

3. **Update the README header.** `README.md` opens with `# Market Data Python SDK vX.Y`.
   It has drifted from the package version before; check it every time.

4. **Promote the CHANGELOG section.** `CHANGELOG.md` is the source of truth for release
   notes, in [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) bracket format.

   - Change `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`.
   - Add a fresh, empty `## [Unreleased]` section above it.
   - Confirm every breaking change carries migration guidance.

   > The file currently has **no `## [Unreleased]` section**. Add one in the next PR that
   > lands a user-visible change, so this step is a promotion rather than an invention.

5. Confirm `README.md` and `docs/` (`stocks.md`, `options.md`, `funds.md`, `markets.md`)
   describe the behavior you are about to ship.

6. Run the gate locally, on the exact commit:

   ```bash
   ./test.sh                    # uv sync && uv run pytest -n 4 --cov="marketdata"
   ./lint.sh                    # black + isort --profile black (this rewrites files)
   uv run black . --check
   uv run isort . --profile black --check-only
   uv build                     # confirm the wheel and sdist build, and check the version
   ls dist/                     # marketdata_sdk_py-X.Y.Z-py3-none-any.whl
   ```

7. Merge the release PR to `main`.

## 4. Cut the release

**There is no `tag-and-release` workflow in this repository.** The tag and the GitHub
Release are created by hand today; `publish.yml` then does the uploading. §6 describes the
workflow that should exist.

1. Confirm the tag is new:

   ```bash
   git fetch --tags && git tag -l "vX.Y.Z"     # must print nothing
   ```

2. Tag the exact commit you validated, and push the tag:

   ```bash
   git checkout main && git pull
   git tag -a vX.Y.Z -m "Version X.Y.Z"
   git push origin vX.Y.Z
   ```

3. Create the GitHub Release from that tag, with notes taken from `CHANGELOG.md`. Existing
   releases are titled `Release vX.Y.Z`.

   ```bash
   gh release create vX.Y.Z --title "Release vX.Y.Z" \
     --notes-file <(awk '/^## \[X\.Y\.Z\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md)
   ```

4. Publishing `vX.Y.Z` — **the point of no return.** The `release: published` event starts
   `publish.yml`:

   | Job | What it does |
   |---|---|
   | `publish-testpypi` | Checks out the release ref, `uv build`, uploads to TestPyPI through the `testpypi` environment |
   | `publish-pypi` | `needs: publish-testpypi`, and gated on `github.event_name == 'release'`. Rebuilds and uploads to PyPI through the `pypi` environment |

   `publish-pypi` is skipped on a manual `workflow_dispatch` run, so dispatching the
   workflow by hand exercises the TestPyPI leg only.

> **`publish.yml` runs no tests.** It builds and uploads. Everything that gates the
> release therefore has to happen before the Release is published — that is what §3 is
> for. Do not treat the green Tests badge on `main` as the release gate unless it is green
> for the exact commit you tagged.

### A release created by a workflow will not trigger `publish.yml`

Releases are created by hand today, so the trigger fires. If a future workflow creates
the Release using the default `GITHUB_TOKEN`, GitHub will **not** start another workflow
run from that event — a guard against recursive triggering — and `publish.yml` will stay
silent. Any automated release must therefore call the publish workflow explicitly
(`workflow_call`) rather than relying on `release: published`.

### The CHANGELOG is written by hand, never by a workflow

There is deliberately no workflow that writes back to `CHANGELOG.md`. Promote
`## [Unreleased]` yourself in the release PR, as §3 describes.

## 5. Post-release checks

1. The GitHub Release exists, with notes matching the `CHANGELOG.md` section.
2. Both `publish.yml` jobs succeeded, and neither was skipped unexpectedly.
3. PyPI serves the new version:

   ```bash
   pip index versions marketdata-sdk-py
   ```

4. A clean environment installs it and reports the version:

   ```bash
   cd "$(mktemp -d)"
   python -m venv .venv && . .venv/bin/activate
   pip install "marketdata-sdk-py==X.Y.Z"
   python -c "from importlib.metadata import version; print(version('marketdata-sdk-py'))"
   python -c "from marketdata import MarketDataClient; print(MarketDataClient().library_version)"
   ```

   The second command constructs a client in demo mode (no token), which is enough to
   prove the package imports and reports its own version. `library_version` is read from
   the installed distribution metadata, so before the upload it could not have answered
   `X.Y.Z`.

5. The extras still resolve:

   ```bash
   pip install "marketdata-sdk-py[pandas]==X.Y.Z"
   pip install "marketdata-sdk-py[polars]==X.Y.Z"
   ```

6. [pypi.org/project/marketdata-sdk-py](https://pypi.org/project/marketdata-sdk-py/)
   renders the README, and the "Development Status" and Python classifiers are right.

## 6. What is missing — the workflow that should exist

Everything in §4 is manual, and §17.5 of the SDK requirements asks for automation. The
gap is recorded here rather than papered over. **No such workflow file exists in this
repository; do not cite one in a PR review as though it did.**

A `tag-and-release.yml` for this SDK, modelled on the one in `MarketDataApp/sdk-csharp`
and `MarketDataApp/sdk-java`, should:

- Trigger **only** on `workflow_dispatch`, with inputs `version`, `ref`, `prerelease` and
  `confirm`, and refuse to proceed unless `confirm` is exactly `RELEASE`.
- **Validate before spending runner time**: `version` is well-formed SemVer without a `v`
  prefix; the tag `vX.Y.Z` does not already exist; `pyproject.toml` declares exactly that
  version; `CHANGELOG.md` contains a `## [X.Y.Z]` section. Print the extracted notes.
- **Call `test.yml`** (`workflow_call`, not a copied job) against the exact ref, so the
  release gate and everyday CI cannot drift apart — including the live integration suite
  (see §7).
- **Resolve `ref` to a concrete commit SHA** and tag that SHA, so a branch moving mid-run
  cannot change what ships.
- Create the tag and the GitHub Release with notes extracted from `CHANGELOG.md`.
- **Call `publish.yml` explicitly** rather than relying on `release: published`, for the
  `GITHUB_TOKEN` reason in §4.
- **Verify after publishing**: poll PyPI for the new version, then install it into a
  throwaway virtualenv and assert `version("marketdata-sdk-py") == X.Y.Z`.

Until that exists, §3 and §4 are the process, and the discipline they describe is the only
gate.

## 7. Repository state this process assumes

| Item | State |
|---|---|
| PyPI Trusted Publishing | configured, through the `pypi` and `testpypi` environments; no API token secret is stored |
| `pypi` / `testpypi` environment protection rules | **none** — no reviewer stands between a published Release and PyPI |
| `MARKETDATA_TOKEN` secret | present; consumed by the `integration` job in `test.yml` |
| Live integration suite | present: `src/tests/integration/`, one live test per endpoint (utilities pending #63), runs on every pull request; a missing token fails the job |
| `CODECOV_TOKEN` secret | present; `test.yml` uploads `coverage.xml` with `fail_ci_if_error: true` |
| `main` branch protection | enabled: `test (3.10)`, `test (3.11)` and `test (3.12)` are required checks; force pushes and deletions are blocked. **No required reviewer**, so a release PR can be merged by its author |
| Default branch | `main` |

> ### The integration suite
>
> `src/tests/integration/` exercises every resource against `api.marketdata.app` with the
> free-trial symbols, asserting on the decoded response shape. It is excluded from the
> default `pytest` run and from `./test.sh`; the `integration` job in `test.yml` runs it on
> every pull request and on manual dispatch, and **fails when `MARKETDATA_TOKEN` is
> absent** rather than skipping (§17.3), so a green pipeline cannot mean "ran nothing".
> Dependabot pull requests cannot read repository secrets, so for them the job is skipped
> as a whole, which the checks list shows as skipped, never as passed.
>
> The suite has not yet been wired into a release gate: until `tag-and-release.yml`
> exists (§6, #61), run it by hand on the exact commit before tagging, and keep the manual
> smoke test in §5 as the final check after publishing.

> ### Coverage is at 100%, and nothing enforces it
>
> `pytest --cov="marketdata"` reports 100% today, but there is no `--cov-fail-under`, no
> `codecov.yml`, and no coverage status check in branch protection. Coverage can fall
> without failing a build. Watch the number in the Tests log during release preparation.

## 8. Rollback and hotfix

A published PyPI version cannot be replaced or re-uploaded.

1. Stop any promotion messaging.
2. **Yank** the bad version so resolvers stop selecting it:

   ```bash
   # PyPI web UI: Manage project → Releases → Options → Yank
   ```

   Yanking is advisory. `pip install marketdata-sdk-py` skips a yanked version, but
   `pip install marketdata-sdk-py==X.Y.Z` still installs it, and existing lockfiles are
   unaffected. Do not delete the release: deletion frees nothing, since the version number
   can never be re-used.
3. Ship a patch release `X.Y.(Z+1)` from `main` with the targeted fix, through §3 and §4.
4. Add a corrective note to the GitHub Release for the bad version, and record the root
   cause and remediation in the next `CHANGELOG.md` entry.

## 9. Related documents

- [`ISSUE_WORKFLOW.md`](./ISSUE_WORKFLOW.md) — triaging an incoming bug report
- [`BUG_FINDING.md`](./BUG_FINDING.md) — the pre-release QA pass
- [`../SECURITY.md`](../SECURITY.md) — vulnerability reporting and the security fix tiers,
  including the rule that publishing a release to PyPI always requires explicit maintainer
  confirmation
