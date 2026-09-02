#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

python "${REPO_ROOT}/scripts/staging_proof.py" "$@"
