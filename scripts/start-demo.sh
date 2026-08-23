#!/usr/bin/env bash
# Demo without Google Sheets: API :8000 + dashboard :5173
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/icebeach-wakeclub"

PYTHON_BIN="python3"
command -v python3 >/dev/null 2>&1 || PYTHON_BIN="python"

cd "${ROOT}/icebeach-wakeclub/apps/dashboard"
if [[ ! -d node_modules ]]; then
  npm ci
fi
cd "${ROOT}"

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "${API_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

"${PYTHON_BIN}" "${ROOT}/scripts/demo_local.py" &
API_PID=$!

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.4
done

if ! curl -fsS "http://127.0.0.1:8000/health"; then
  echo "API failed to start on :8000" >&2
  exit 1
fi
echo

echo "Dashboard: http://127.0.0.1:5173"
echo "API:       http://127.0.0.1:8000/health"
echo "Вход: Админ / Оператор / Пилот на форме логина (DEV-код на экране)"
echo "Ctrl+C — остановить demo"
echo

cd "${ROOT}/icebeach-wakeclub/apps/dashboard"
npm run dev -- --host 0.0.0.0 --port 5173
