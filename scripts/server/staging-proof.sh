#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "python3 or python is required for staging proof" >&2
  exit 1
fi

exec "${PYTHON_BIN}" "${REPO_ROOT}/scripts/staging_proof.py" "$@"
