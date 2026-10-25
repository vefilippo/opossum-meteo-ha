#!/usr/bin/env bash
# Runs the test suite inside Docker (Home Assistant does not run natively on Windows).
export MSYS_NO_PATHCONV=1   # keep Git Bash on Windows from rewriting /w
SRC="$(pwd -W 2>/dev/null || pwd)"
docker run --rm -v "$SRC":/w -v ha-pip-cache:/root/.cache/pip -w /w python:3.13 \
  sh -c "pip install -q -r requirements_test.txt && pytest -q"
