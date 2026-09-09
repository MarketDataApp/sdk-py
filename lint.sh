#!/bin/bash
# Rewrites files, then reports whether anything is still wrong. CI runs the
# same commands in check mode (.github/workflows/lint.yml), and the pre-commit
# hooks run them on staged files.
PATHS="src/ examples/ .github/scripts/"

uv run python .github/scripts/check_ruff_version.py
version_status=$?

uv run ruff check --fix $PATHS
check_status=$?

uv run ruff format $PATHS
format_status=$?

# A violation ruff cannot fix (E741, F811, F821) leaves a non-zero status that
# the formatter would otherwise hide behind its own success.
exit $(( version_status || check_status || format_status ))
