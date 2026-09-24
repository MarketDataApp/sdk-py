"""`.github/scripts/check_ruff_version.py` keeps every pre-commit hook on the ruff
that uv.lock pins: each way of running or pinning another ruff is reported."""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "check_ruff_version.py"
CONFIG = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

CHECK_ENTRY = "entry: uv run ruff check --force-exclude"
FORMAT_ENTRY = "entry: uv run ruff format --force-exclude"
UNIT_TESTS = "      - id: unit_tests\n"
PINNED_REPO = (
    "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
    "    rev: v0.16.7\n"
    "    hooks:\n"
    "      - id: ruff-check\n"
    "        args: [--fix]\n"
    "      - id: ruff-format\n"
    "\n"
)


def with_hook(*lines: str) -> tuple[str, str]:
    """An edit that adds a local hook made of `lines` before `unit_tests`.

    Args:
        *lines: The hook's lines, its first key first, without indentation.

    Returns:
        The text to replace and its replacement.
    """
    first, *rest = lines
    hook = f"      - {first}\n" + "".join(f"        {line}\n" for line in rest)
    return UNIT_TESTS, hook + UNIT_TESTS


@pytest.fixture
def checker(monkeypatch, tmp_path):
    """The script loaded as a module that reads its pre-commit config from `tmp_path`.

    Returns:
        The module, with `REPO_ROOT` and `PRE_COMMIT_CONFIG` inside `tmp_path`.
    """
    spec = importlib.util.spec_from_file_location("check_ruff_version", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        module, "PRE_COMMIT_CONFIG", tmp_path / ".pre-commit-config.yaml"
    )
    return module


def problems_for(checker, text: str) -> list[str]:
    """What the checker reports for a pre-commit config that reads `text`.

    Args:
        checker: The module from the `checker` fixture.
        text: The whole pre-commit config.

    Returns:
        The problems `_pre_commit_problems()` reports, one line each.
    """
    checker.PRE_COMMIT_CONFIG.write_text(text, encoding="utf-8")
    return checker._pre_commit_problems()


def test_the_committed_pre_commit_config_passes(checker):
    """The config in the repo runs both ruff hooks through uv, and nothing else names ruff."""
    assert problems_for(checker, CONFIG) == []


def test_a_hook_whose_words_only_contain_ruff_passes(checker):
    """A hook such as `trufflehog` does not name ruff, so it is not reported."""
    old, new = with_hook(
        "id: trufflehog",
        "name: TruffleHog",
        "entry: trufflehog git file://. --since-commit HEAD --fail",
        "language: system",
        "pass_filenames: false",
    )
    assert old in CONFIG

    assert problems_for(checker, CONFIG.replace(old, new, 1)) == []


def test_a_missing_pre_commit_config_is_reported(checker):
    """No config at all is a problem, not a config with nothing to check."""
    assert checker._pre_commit_problems() == [
        "  .pre-commit-config.yaml: the pre-commit config is missing"
    ]


@pytest.mark.parametrize(
    ("edits", "expected"),
    [
        pytest.param(
            [("repos:\n", "repos:\n" + PINNED_REPO)],
            "ruff-pre-commit repo, whose rev is a second ruff version",
            id="the pinned ruff-pre-commit repo added back",
        ),
        pytest.param(
            [(CHECK_ENTRY, "entry: ruff check --force-exclude")],
            "the `ruff-check` hook does not run `uv run ruff check`",
            id="ruff check without uv",
        ),
        pytest.param(
            [(FORMAT_ENTRY, "entry: ruff format --force-exclude")],
            "the `ruff-format` hook does not run `uv run ruff format`",
            id="ruff format without uv",
        ),
        pytest.param(
            [("- id: ruff-check ", "- id: ruff-lint ")],
            "the `ruff-check` hook does not run `uv run ruff check`",
            id="no ruff-check hook",
        ),
        pytest.param(
            [(CHECK_ENTRY, "entry: ruff check --force-exclude  # uv run ruff check")],
            "the `ruff-check` hook does not run `uv run ruff check`",
            id="uv run ruff check only in a comment",
        ),
        pytest.param(
            [
                (
                    "name: ruff check\n        " + CHECK_ENTRY,
                    "name: uv run ruff check\n        entry: ruff check --force-exclude",
                )
            ],
            "the `ruff-check` hook does not run `uv run ruff check`",
            id="uv run ruff check only in the hook's name",
        ),
        pytest.param(
            [
                (
                    CHECK_ENTRY + "\n        args: [--fix]",
                    "entry: ruff check --force-exclude\n"
                    "        args: [--fix, uv run ruff check]",
                )
            ],
            "the `ruff-check` hook does not run `uv run ruff check`",
            id="uv run ruff check only in the hook's args",
        ),
        pytest.param(
            [
                (CHECK_ENTRY, "entry: ruff check --force-exclude"),
                with_hook(
                    "id: ruff-version",
                    "name: ruff version",
                    "entry: uv run ruff check --version",
                    "language: system",
                    "pass_filenames: false",
                ),
            ],
            "the `ruff-check` hook does not run `uv run ruff check`",
            id="uv run ruff check only in another hook's entry",
        ),
        pytest.param(
            [
                with_hook(
                    "id: ruff-docs",
                    "name: ruff docs",
                    "entry: ruff format --force-exclude docs/",
                    "language: system",
                )
            ],
            "`entry: ruff format --force-exclude docs/` names ruff",
            id="another hook running ruff without uv",
        ),
        pytest.param(
            [
                with_hook(
                    "id: lint",
                    "name: lint",
                    "entry: python -m ruff check",
                    "language: system",
                )
            ],
            "`entry: python -m ruff check` names ruff",
            id="python -m ruff",
        ),
        pytest.param(
            [
                with_hook(
                    "id: lint",
                    "name: lint",
                    "entry: env ruff check",
                    "language: system",
                )
            ],
            "`entry: env ruff check` names ruff",
            id="env ruff",
        ),
        pytest.param(
            [
                with_hook(
                    "id: lint",
                    "name: lint",
                    "entry: sh -c 'ruff check'",
                    "language: system",
                )
            ],
            "`entry: sh -c 'ruff check'` names ruff",
            id="sh -c ruff",
        ),
        pytest.param(
            [
                with_hook(
                    "id: lint",
                    "name: lint",
                    "entry: >-",
                    "  ruff check",
                    "language: system",
                )
            ],
            "`ruff check` names ruff",
            id="ruff on the continuation of a multi-line entry",
        ),
        pytest.param(
            [
                (
                    CHECK_ENTRY,
                    CHECK_ENTRY + "\n        additional_dependencies: [ruff==0.16.0]",
                )
            ],
            "`additional_dependencies: [ruff==0.16.0]` names ruff",
            id="ruff pinned in additional_dependencies",
        ),
        pytest.param(
            [
                (
                    UNIT_TESTS,
                    "      - {id: lint, name: lint, entry: ruff check, language: system}\n"
                    + UNIT_TESTS,
                )
            ],
            "`- {id: lint, name: lint, entry: ruff check, language: system}` names ruff",
            id="a hook written as a flow mapping",
        ),
    ],
)
def test_a_pre_commit_config_that_runs_another_ruff_is_reported(
    checker, edits, expected
):
    """Each way of running ruff outside uv, or of pinning another ruff, is reported.

    Args:
        checker: The module from the `checker` fixture.
        edits: Replacements applied in order to the committed config.
        expected: Text that one of the reported problems must contain.
    """
    text = CONFIG
    for old, new in edits:
        assert old in text, f"the committed config no longer contains {old!r}"
        text = text.replace(old, new, 1)

    problems = problems_for(checker, text)

    assert any(expected in problem for problem in problems), problems
