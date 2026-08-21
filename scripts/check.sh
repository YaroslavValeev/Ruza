#!/usr/bin/env bash
# One-command checks: API contract tests + dashboard typecheck/build.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/icebeach-wakeclub"

PYTHON_BIN="python3"
command -v python3 >/dev/null 2>&1 || PYTHON_BIN="python"

"${PYTHON_BIN}" -m pytest "${ROOT}/icebeach-wakeclub/apps/api/tests" -v

cd "${ROOT}/icebeach-wakeclub/apps/dashboard"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npx tsc --noEmit
npm run build

echo
echo "OK: tests + dashboard build"
