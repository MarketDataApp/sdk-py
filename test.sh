#!/bin/bash
uv sync
uv run pytest -n 4 --cov="marketdata"
