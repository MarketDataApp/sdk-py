"""Assert that every place this repo runs ruff uses the one build uv.lock pins.

The lint job installs ruff from `uv.lock`, so the locked version is the one that
judges every pull request, and `uv.lock` is the only file that names it:

  - `pyproject.toml` declares the floor, in the `dev` dependency group, and the
    locked version must satisfy it;
  - `.pre-commit-config.yaml` must run both ruff hooks through uv
    (`uv run ruff`) and must not use the `ruff-pre-commit` repo, whose `rev`
    would be a second version to keep in step with the lock;
  - `.github/workflows/lint.yml` must run ruff through uv (`uv run ruff`) and
    must not `pip install` it, which would take whatever release is newest that
    day and turn open pull requests red on untouched code.

A ruff bump is therefore `uv lock --upgrade-package ruff` alone. Run this after
it, and before changing any ruff declaration:

    uv run python .github/scripts/check_ruff_version.py
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

try:  # tomllib is 3.11+, and this package still supports 3.10
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - depends on the interpreter
    tomllib = None

REPO_ROOT = Path(__file__).resolve().parents[2]

PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCKFILE = REPO_ROOT / "uv.lock"
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
LINT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "lint.yml"

# A ruff requirement such as `ruff>=0.16.0`, capturing operator and version
# separately so the floor can be extracted.
_REQUIREMENT = re.compile(r"ruff\s*(==|>=|~=)\s*([0-9][0-9A-Za-z.\-+]*)")

# The `[[package]]` block of uv.lock that pins ruff.
_LOCKED = re.compile(
    r'\[\[package\]\]\s*name\s*=\s*"ruff"\s*version\s*=\s*"([^"]+)"', re.S
)

# The pre-commit hooks that run ruff, and the command each entry must start with.
_RUFF_HOOKS = {"ruff-check": "uv run ruff check", "ruff-format": "uv run ruff format"}


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _version_key(version: str) -> tuple[int, ...]:
    """Sortable key for a simple X.Y.Z version; unparsable parts sort as 0."""
    numbers = re.findall(r"\d+", version)
    return tuple(int(number) for number in numbers[:3]) or (0,)


def _without_comments(text: str) -> str:
    """`text` with every `#` comment removed.

    The workflow explains in prose what it must not do, naming the very
    commands this script looks for, so reading the file line by line without
    its comments is what keeps a comment from standing in for the real step.
    """
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _dev_group_requirements() -> list[str]:
    """The entries of the `dev` dependency group of pyproject.toml.

    Parsed with tomllib where it exists. On 3.10, which this package still
    supports and a contributor may well be running, the group is read with a
    scoped regex rather than pulling in a TOML backport for one lookup.
    """
    if not PYPROJECT.is_file():
        return []
    text = PYPROJECT.read_text(encoding="utf-8")
    if tomllib is not None:
        groups = tomllib.loads(text).get("dependency-groups", {})
        return [entry for entry in groups.get("dev", []) if isinstance(entry, str)]
    match = re.search(r"^dev\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    if match is None:
        return []
    return re.findall(r"""['"]([^'"]+)['"]""", match.group(1))


def _declared_floor() -> str | None:
    """The ruff requirement declared in the pyproject dev dependency group."""
    for requirement in _dev_group_requirements():
        match = _REQUIREMENT.fullmatch(requirement.strip())
        if match:
            return f"ruff{match.group(1)}{match.group(2)}"
    return None


def _locked_version() -> str | None:
    """The exact ruff version pinned by uv.lock."""
    if not LOCKFILE.is_file():
        return None
    match = _LOCKED.search(LOCKFILE.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _installed_ruff_version() -> str | None:
    """Version of the ruff belonging to this interpreter, or None if absent.

    The ruff installed alongside `sys.executable` wins over whatever PATH
    happens to resolve first: both `uv run` and `uv sync` put it there, whereas
    a bare `python` invocation would otherwise pick up an unrelated global ruff
    and report a mismatch that has nothing to do with this repo.
    """
    scripts_dir = Path(sys.executable).parent
    local = next(
        (
            candidate
            for name in ("ruff", "ruff.exe")
            if (candidate := scripts_dir / name).is_file()
        ),
        None,
    )
    executable = str(local) if local is not None else shutil.which("ruff")
    if executable is None:
        return None
    try:
        output = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):  # a broken ruff is not a drift
        return None
    match = re.search(r"(\d+\.\d+\.\d+\S*)", output)
    return match.group(1) if match else None


def _workflow_problems() -> list[str]:
    """How the lint workflow installs and calls ruff, comments excluded."""
    if not LINT_WORKFLOW.is_file():
        return [f"  {_rel(LINT_WORKFLOW)}: the lint workflow is missing"]

    commands = _without_comments(LINT_WORKFLOW.read_text(encoding="utf-8"))
    problems = []
    if re.search(r"pip install[^\n]*ruff", commands):
        problems.append(
            f"  {_rel(LINT_WORKFLOW)}: installs ruff with pip, which ignores "
            "uv.lock and takes the newest release; run it through `uv run ruff`"
        )
    if "uv sync" not in commands:
        problems.append(f"  {_rel(LINT_WORKFLOW)}: does not install the locked deps")
    for command in ("uv run ruff check", "uv run ruff format --check"):
        if command not in commands:
            problems.append(f"  {_rel(LINT_WORKFLOW)}: does not run `{command}`")
    return problems


def _pre_commit_items() -> list[dict[str, str]]:
    """The repos and hooks of the pre-commit config, comments excluded.

    Read line by line so the script needs no YAML library: a `- key: value` line
    starts an item, and each `key: value` line after it fills that item in. An
    item written as a flow mapping is kept as `unreadable`, never skipped.

    Returns:
        One mapping of key to unquoted value per repo and per hook, in file order.
    """
    items: list[dict[str, str]] = []
    text = _without_comments(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    for line in text.splitlines():
        if re.match(r"\s*-\s*\{", line):
            items.append({"unreadable": line.strip()})
            continue
        match = re.match(r"\s*(-\s+)?([\w-]+):(.*)", line)
        if match is None:
            continue
        starts_item, key, value = match.groups()
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if starts_item:
            items.append({})
        if items:
            items[-1][key] = value
    return items


def _pre_commit_problems() -> list[str]:
    """How the pre-commit hooks call ruff, read from each hook's own `entry`.

    Returns:
        One line per problem, empty when every `ruff-check` and `ruff-format`
        hook runs its command through uv, no other hook runs ruff without uv and
        no hook repo pins a ruff version of its own.
    """
    config = _rel(PRE_COMMIT_CONFIG)
    if not PRE_COMMIT_CONFIG.is_file():
        return [f"  {config}: the pre-commit config is missing"]

    items = _pre_commit_items()
    problems = [
        f"  {config}: cannot read `{item['unreadable']}`; write it as a block mapping"
        for item in items
        if "unreadable" in item
    ]
    if any("ruff-pre-commit" in item.get("repo", "") for item in items):
        problems.append(
            f"  {config}: uses the ruff-pre-commit repo, whose rev is a second "
            "ruff version; run the hooks through `uv run ruff`"
        )
    for hook_id, command in _RUFF_HOOKS.items():
        entries = [item.get("entry", "") for item in items if item.get("id") == hook_id]
        expected = command.split()
        if not entries or any(
            entry.split()[: len(expected)] != expected for entry in entries
        ):
            problems.append(
                f"  {config}: the `{hook_id}` hook does not run `{command}`"
            )
    for item in items:
        words = item.get("entry", "").split()
        if (
            item.get("id") not in _RUFF_HOOKS
            and words
            and Path(words[0]).stem == "ruff"
        ):
            problems.append(
                f"  {config}: the `{item.get('id')}` hook runs ruff without uv"
            )
    return problems


def main() -> int:
    """Check every ruff declaration against the version uv.lock pins.

    Returns:
        0 when they agree, or 1 after printing each disagreement to stderr.
    """
    floor_requirement = _declared_floor()
    if floor_requirement is None:
        print(
            "ERROR: no ruff requirement found in the `dev` dependency group of "
            f"{_rel(PYPROJECT)}.",
            file=sys.stderr,
        )
        return 1

    floor = _REQUIREMENT.fullmatch(floor_requirement).group(2)
    problems = _workflow_problems()

    locked = _locked_version()
    if locked is None:
        problems.append(f"  {_rel(LOCKFILE)}: no ruff package found")
    elif _version_key(locked) < _version_key(floor):
        problems.append(f"  {_rel(LOCKFILE)}: pins {locked}, below the {floor} floor")

    problems.extend(_pre_commit_problems())

    installed = _installed_ruff_version()
    # No ruff installed is fine: the declarations are still checkable.
    if installed is not None and locked is not None and installed != locked:
        problems.append(
            f"  installed ruff: {installed} is not the locked {locked}; run `uv sync`"
        )

    if problems:
        print(
            "ERROR: the ruff declarations disagree:\n" + "\n".join(problems) + "\n\n"
            f"{_rel(PYPROJECT)} declares {floor_requirement} and {_rel(LOCKFILE)} "
            f"pins {locked}. Update every location together.",
            file=sys.stderr,
        )
        return 1

    print(
        f"ruff {locked} everywhere: {_rel(PYPROJECT)} floor {floor_requirement}, "
        f"{_rel(LOCKFILE)} pin, pre-commit hooks and lint workflow through uv."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
