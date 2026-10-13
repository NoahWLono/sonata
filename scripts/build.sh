#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python scripts/sync_examples.py
.venv/bin/python -m pytest tests/test_milestone.py -q
.venv/bin/python scripts/milestone.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/build.py
.venv/bin/python scripts/v1_demos.py
.venv/bin/python experiments/analyze.py --root .
.venv/bin/python scripts/study.py generate --root .
.venv/bin/python scripts/video.py
.venv/bin/python scripts/check_artifacts.py
