#!/bin/sh
set -eu
mkdir -p reports
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m pytest -q -rA --junitxml=reports/junit.xml "$@"
