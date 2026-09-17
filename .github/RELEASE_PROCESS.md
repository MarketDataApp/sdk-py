# Python SDK Release Process

This document defines the release process for `MarketDataApp/sdk-py`. The package is
[`marketdata-sdk-py`](https://pypi.org/project/marketdata-sdk-py/) on PyPI.

## 1. What "publishing" means for Python

A release is an **upload to PyPI**. `uv build` produces a wheel and an sdist from the
version declared in `pyproject.toml`, and `pypa/gh-action-pypi-publish` uploads them.

That has three consequences that shape everything below.

| | |
|---|---|
| **The version comes from `pyproject.toml`, not from the tag** | `[project] version = "X.Y.Z"` is a static string (hatchling). Bump it in the release PR: `tag-and-release` refuses to run when that number and the version it was asked for disagree, and `publish.yml` refuses to upload a build that does not carry it (#61). |
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
`marketdata.exceptions` is produced for a given failure; changing the fields of
`support_context` / `support_info`; changing a user-visible default (`output_format`,
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

   > `tag-and-release` refuses to run without a `## [X.Y.Z]` section for the version it
   > was asked for, and it takes the release notes from that section alone.

5. Confirm `README.md` and `docs/` (`stocks.md`, `options.md`, `funds.md`, `markets.md`)
   describe the behavior you are about to ship.

6. Run the gate locally, on the exact commit:

   ```bash
   ./test.sh                    # uv sync && uv run pytest -n 4 --cov="marketdata"
   ./lint.sh                    # ruff check --fix + ruff format (this rewrites files)
   uv run ruff check src/ examples/ .github/scripts/
   uv run ruff format --check src/ examples/ .github/scripts/
   uv run pytest src/tests/integration -m integration   # the live suite, which
                                # `./test.sh` excludes and the release gate requires
   uv build                     # confirm the wheel and sdist build, and check the version
   ls dist/                     # marketdata_sdk_py-X.Y.Z-py3-none-any.whl
   ```

7. Merge the release PR to `main`.

## 4. Cut the release

`tag-and-release.yml` does this, and it is the only path that runs the suite before the
tag exists. Actions tab → **Tag and release** → *Run workflow*, from `main`:

| Input | What to put there |
|---|---|
| `version` | `X.Y.Z`, no `v`. The same number the release PR wrote into `pyproject.toml` |
| `ref` | the branch or commit to release, normally `main` |
| `prerelease` | tick it for `X.Y.Zrc1` and the like; it only marks the GitHub Release |
| `confirm` | `RELEASE`, typed. Anything else stops the run before it does anything |

What runs, in order:

| Stage | What it does |
|---|---|
| `validate` | Before any runner time is spent: `confirm` is `RELEASE`, the version is well formed, the tag `vX.Y.Z` does not exist, `pyproject.toml` declares exactly that version, and `CHANGELOG.md` has a `## [X.Y.Z]` section. It prints the notes it extracted |
| `gate` | Calls `test.yml` on that ref with `run_integration: true`: the suite on Python 3.10, 3.11 and 3.12 **and** the live integration suite, which here must run rather than skip |
| `release` | Resolves the ref to a commit, checks the tag again in case one appeared while the suite ran, and creates the tag and the GitHub Release on that commit, titled `Version X.Y.Z`, with the notes from the CHANGELOG |
| `publish` | Calls `publish.yml` on that commit: TestPyPI first, then PyPI, both through Trusted Publishing. It refuses to upload a build whose version is not the one asked for. Its own gate is skipped here, since `gate` above already ran the suite on this commit |
| `verify` | Polls PyPI for the version, then installs it into a throwaway environment and reads its version back |

Two things the workflow does not do, on purpose:

- **It does not write to the repository.** The version bump and the CHANGELOG promotion
  are the release PR's job (§3), so what ships is reviewed like any other change.
- **It does not release a commit that is not on `main`.** A dispatch takes any ref the
  repository can check out, a pull request's merge ref included, and the code at that ref
  then runs with the publishing credentials. `validate` refuses a commit `main` does not
  contain.

Changing the workflow itself is awkward, and that is worth knowing before you do: the
button only appears for workflows on the default branch, though it then runs the copy on
the branch you pick. So a change to the release path can be rehearsed from a branch, but
only up to the point where it would create the tag.

> **The point of no return is the `publish` stage.** Everything before it can be re-run;
> a `(name, version)` pair on PyPI, and on TestPyPI, is permanent (§1).

If the workflow itself is broken, the manual path still works: tag the commit, push the
tag, and create the Release. The `release: published` event starts `publish.yml`, which
carries the same gates on that path, since a release anyone with write access can create
must not be a way around them: it resolves the tag to a commit once, refuses one `main`
does not contain or that the CHANGELOG has no section for, runs the suite and the live
suite on that commit, and checks the version against `pyproject.toml` before it uploads.
What it cannot do is check anything before the tag exists.

```bash
git fetch --tags && git tag -l "vX.Y.Z"     # must print nothing
git checkout main && git pull
git tag -a vX.Y.Z -m "Version X.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "Version X.Y.Z" --notes-file <(awk '/^## \[X\.Y\.Z\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md)
```

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

> The `verify` stage of `tag-and-release` covers part of 3 and 4 on its own: it polls
> PyPI's JSON API for the version and installs the package into a throwaway environment,
> where it reads the version back from the distribution metadata. It does not construct a
> client, and it does not touch the extras, so 4's second command and 5 are still worth
> running by hand.

## 6. What the release path still does not cover

`tag-and-release.yml` closed the gap this section used to describe (#61). What is left:

- **Nothing stands between a published Release and PyPI.** The `pypi` and `testpypi`
  environments carry no protection rules, so no reviewer is asked. Required reviewers on
  the `pypi` environment are a repository setting, not a file in this repository.
- **Coverage is not enforced anywhere** (see the note at the end of §7).
- **A half-finished release is recovered by hand.** If `publish` fails after the tag and
  the Release exist, the release is real and the files are not. Dispatching
  `tag-and-release` again does not help: it refuses the tag that now exists. Fix the
  cause, then either re-run the failed jobs of that run, or delete the GitHub Release and
  create it again from the same tag, which starts `publish.yml` through its `release`
  trigger and runs its gate again on the way. The TestPyPI leg skips files it already
  uploaded, so a second attempt reaches PyPI.

## 7. Repository state this process assumes

| Item | State |
|---|---|
| PyPI Trusted Publishing | configured, through the `pypi` and `testpypi` environments; no API token secret is stored |
| `pypi` / `testpypi` environment protection rules | **none** — no reviewer stands between a published Release and PyPI |
| `MARKETDATA_TOKEN` secret | present; consumed by the `integration` job in `test.yml` |
| Live integration suite | present: `src/tests/integration/`, one live test per endpoint, runs on every pull request that changes something other than documentation; a missing token fails the job |
| `CODECOV_TOKEN` secret | present; `test.yml` uploads `coverage.xml` with `fail_ci_if_error: false`, so a dependabot run, which cannot read it, does not turn red on the upload |
| `main` branch protection | enabled: `Tests passed` is the required check; force pushes and deletions are blocked. **No required reviewer**, so a release PR can be merged by its author |
| Default branch | `main` |

> ### The integration suite
>
> `src/tests/integration/` exercises every resource against `api.marketdata.app` with the
> free-trial symbols, asserting on the decoded response shape. It is excluded from the
> default `pytest` run and from `./test.sh`; the `integration` job in `test.yml` runs it on
> every pull request that changes something other than documentation, and on manual
> dispatch, and **fails when `MARKETDATA_TOKEN` is absent** rather than skipping (§17.3),
> so a green pipeline cannot mean "ran nothing".
> Dependabot pull requests cannot read repository secrets, so for them the job is skipped
> as a whole, which the checks list shows as skipped, never as passed.
>
> The `gate` stage of `tag-and-release` runs it on the exact commit before the tag
> exists, with `run_integration: true`, and there a skipped live suite fails the gate
> instead of passing it (#61). The smoke test in §5 stays as the check after publishing.

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
