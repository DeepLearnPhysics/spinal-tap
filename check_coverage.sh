#!/usr/bin/env bash

set -euo pipefail

test_path="${1:-test}"
coverage_target="${2:-spinal_tap}"
python_bin="${PYTHON:-.venv/bin/python}"

PYTHONPATH="src:${PYTHONPATH:-}" "$python_bin" -m pytest "$test_path" \
  --override-ini addopts= \
  --cov="$coverage_target" \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --maxfail=10
