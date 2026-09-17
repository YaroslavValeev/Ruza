#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

PYTHON_CMD=()
if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=(python3)
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD=(python)
elif command -v py >/dev/null 2>&1; then
  PYTHON_CMD=(py -3)
elif command -v py.exe >/dev/null 2>&1; then
  PYTHON_CMD=(py.exe -3)
else
  echo "[BLOCKER] python3/python/py not found"
  exit 1
fi

PORT_FILE="${TMP_DIR}/port"
SERVER_LOG="${TMP_DIR}/server.log"

"${PYTHON_CMD[@]}" - "${PORT_FILE}" >"${SERVER_LOG}" 2>&1 <<'PY' &
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

port_file = sys.argv[1]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            return
        if self.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<!doctype html><html>Ice Beach</html>")
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/alert":
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length)
            self.send_response(200)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format, *_args):
        return

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
with open(port_file, "w", encoding="utf-8") as fh:
    fh.write(str(server.server_port))
server.serve_forever()
PY
SERVER_PID=$!

for _ in $(seq 1 50); do
  [[ -s "${PORT_FILE}" ]] && break
  sleep 0.1
done

if [[ ! -s "${PORT_FILE}" ]]; then
  echo "[BLOCKER] mock server did not start"
  cat "${SERVER_LOG}" || true
  kill "${SERVER_PID}" 2>/dev/null || true
  exit 1
fi

PORT="$(cat "${PORT_FILE}")"
BASE_URL="http://127.0.0.1:${PORT}"

set +e
GOOD_OUTPUT="$(bash "${REPO_ROOT}/scripts/server/healthcheck.sh" --api-url "${BASE_URL}" --dashboard-url "${BASE_URL}/dashboard" --log-file "${TMP_DIR}/health.log" 2>&1)"
GOOD_STATUS=$?
BAD_OUTPUT="$(bash "${REPO_ROOT}/scripts/server/healthcheck.sh" --api-url "${BASE_URL}/missing" --alert-webhook-url "${BASE_URL}/alert" 2>&1)"
BAD_STATUS=$?
set -e

kill "${SERVER_PID}" 2>/dev/null || true

echo "${GOOD_OUTPUT}"
echo "${BAD_OUTPUT}"

if [[ "${GOOD_STATUS}" -ne 0 || "${GOOD_OUTPUT}" != *"SUMMARY blockers=0"* ]]; then
  echo "[BLOCKER] healthcheck success case failed"
  exit 1
fi

if [[ ! -s "${TMP_DIR}/health.log" ]]; then
  echo "[BLOCKER] healthcheck did not write log file"
  exit 1
fi

if [[ "${BAD_STATUS}" -eq 0 || "${BAD_OUTPUT}" != *"[BLOCKER] api.health"* || "${BAD_OUTPUT}" != *"[PASS] alert.webhook"* ]]; then
  echo "[BLOCKER] healthcheck failure/alert case failed"
  exit 1
fi

echo "[PASS] server healthcheck behavior verified"
