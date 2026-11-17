#!/usr/bin/env bash

set -euo pipefail

EXPECTED_DIR="backend"
CURRENT_DIR=$(basename "$PWD")

if [ "$CURRENT_DIR" != "$EXPECTED_DIR" ]; then
  echo "Error: You must run this script from the '$EXPECTED_DIR' directory."
  exit 1
fi

uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest --maxfail=1
