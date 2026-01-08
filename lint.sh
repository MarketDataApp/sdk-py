#!/bin/bash
uv run black .
uv run isort --profile black .
