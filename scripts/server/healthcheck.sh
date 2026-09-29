#!/usr/bin/env bash
set -euo pipefail

API_URL=""
DASHBOARD_URL=""
LOG_FILE=""
ALERT_WEBHOOK_URL=""
TIMEOUT_SECONDS="10"
PYTHON_CMD=()

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/server/healthcheck.sh --api-url https://api.example.com [options]

Options:
  --dashboard-url URL       Also check dashboard HTTP 200.
  --log-file PATH           Append probe output to this file.
  --alert-webhook-url URL   POST a compact JSON alert only when blockers > 0.
  --timeout-seconds N       curl timeout in seconds, default 10.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url)
      API_URL="${2:-}"
      shift 2
      ;;
    --dashboard-url)
      DASHBOARD_URL="${2:-}"
      shift 2
      ;;
    --log-file)
      LOG_FILE="${2:-}"
      shift 2
      ;;
    --alert-webhook-url)
      ALERT_WEBHOOK_URL="${2:-}"
      shift 2
      ;;
    --timeout-seconds)
      TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

BLOCKERS=0
OUTPUT_LINES=()

emit() {
  local line="$1"
  OUTPUT_LINES+=("${line}")
  echo "${line}"
}

pass() {
  emit "[PASS] $1: $2"
}

blocker() {
  emit "[BLOCKER] $1: $2"
  BLOCKERS=$((BLOCKERS + 1))
}

join_url() {
  local base="${1%/}"
  local path="${2#/}"
  echo "${base}/${path}"
}

check_http_ok() {
  local code="$1"
  local url="$2"
  local response_file
  response_file="$(mktemp)"
  local http_code
  http_code="$(curl -fsS --max-time "${TIMEOUT_SECONDS}" -o "${response_file}" -w '%{http_code}' "${url}" 2>/dev/null || true)"
  if [[ "${http_code}" == "200" ]]; then
    pass "${code}" "200 ${url}"
    rm -f "${response_file}"
    return 0
  fi
  blocker "${code}" "expected 200 from ${url}, got ${http_code:-curl_error}"
  rm -f "${response_file}"
  return 1
}

check_api_health() {
  local health_url
  health_url="$(join_url "${API_URL}" "/health")"
  local response_file
  response_file="$(mktemp)"
  local http_code
  http_code="$(curl -fsS --max-time "${TIMEOUT_SECONDS}" -o "${response_file}" -w '%{http_code}' "${health_url}" 2>/dev/null || true)"
  if [[ "${http_code}" != "200" ]]; then
    blocker "api.health" "expected 200 from ${health_url}, got ${http_code:-curl_error}"
    rm -f "${response_file}"
    return 1
  fi
  if grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' "${response_file}"; then
    pass "api.health" "status ok"
  else
    blocker "api.health" "response is 200 but status is not ok"
  fi
  rm -f "${response_file}"
}

find_python() {
  if [[ "${#PYTHON_CMD[@]}" -gt 0 ]]; then
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=(python3)
  elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=(python)
  elif command -v py >/dev/null 2>&1; then
    PYTHON_CMD=(py -3)
  elif command -v py.exe >/dev/null 2>&1; then
    PYTHON_CMD=(py.exe -3)
  else
    blocker "alert.webhook" "python is required to build alert payload"
    return 1
  fi
}

send_alert_if_needed() {
  if [[ "${BLOCKERS}" -eq 0 || -z "${ALERT_WEBHOOK_URL}" ]]; then
    return 0
  fi
  find_python || return 0
  local payload
  payload="$("${PYTHON_CMD[@]}" - <<PY
import json
print(json.dumps({
  "service": "ruza",
  "severity": "critical",
  "blockers": ${BLOCKERS},
  "message": "Ruza healthcheck failed"
}))
PY
)"
  if curl -fsS --max-time "${TIMEOUT_SECONDS}" -H 'Content-Type: application/json' -d "${payload}" "${ALERT_WEBHOOK_URL}" >/dev/null 2>&1; then
    pass "alert.webhook" "alert delivered"
  else
    blocker "alert.webhook" "failed to deliver alert"
  fi
}

if [[ -z "${API_URL}" ]]; then
  echo "--api-url is required" >&2
  usage >&2
  exit 2
fi

emit "=== RUZA SERVER HEALTHCHECK ==="
emit "API: ${API_URL}"
if [[ -n "${DASHBOARD_URL}" ]]; then
  emit "Dashboard: ${DASHBOARD_URL}"
fi

check_api_health || true
if [[ -n "${DASHBOARD_URL}" ]]; then
  check_http_ok "dashboard.http" "${DASHBOARD_URL}" || true
fi
send_alert_if_needed

emit "SUMMARY blockers=${BLOCKERS}"

if [[ -n "${LOG_FILE}" ]]; then
  mkdir -p "$(dirname "${LOG_FILE}")"
  {
    date -Is
    printf '%s\n' "${OUTPUT_LINES[@]}"
    echo ""
  } >> "${LOG_FILE}"
fi

if [[ "${BLOCKERS}" -gt 0 ]]; then
  exit 1
fi
