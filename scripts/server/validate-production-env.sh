#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env.docker}"
BLOCKERS=0

pass() {
  echo "[PASS] $1: $2"
}

blocker() {
  echo "[BLOCKER] $1: $2"
  BLOCKERS=$((BLOCKERS + 1))
}

declare -A ENV_MAP=()

read_env_file() {
  local file="$1"
  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    local line="${raw_line#"${raw_line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    [[ "${line}" != *=* ]] && continue
    local key="${line%%=*}"
    local value="${line#*=}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    ENV_MAP["${key}"]="${value}"
  done < "${file}"
}

value() {
  local key="$1"
  echo "${ENV_MAP[${key}]:-}"
}

require_value() {
  local key="$1"
  local val
  val="$(value "${key}")"
  if [[ -z "${val}" ]]; then
    blocker "${key}" "missing or empty"
  else
    pass "${key}" "present"
  fi
}

require_exact() {
  local key="$1"
  local expected="$2"
  local val
  val="$(value "${key}")"
  if [[ "${val}" == "${expected}" ]]; then
    pass "${key}" "${expected}"
  else
    blocker "${key}" "expected '${expected}', got '${val}'"
  fi
}

block_placeholder() {
  local key="$1"
  local val
  val="$(value "${key}")"
  [[ -z "${val}" ]] && return 0
  if [[ "${val}" =~ replace|change-me|your_|example\.com|example/ || "${val}" == *"<"* || "${val}" == *">"* ]]; then
    blocker "${key}" "contains placeholder/example value"
  fi
}

require_https() {
  local key="$1"
  local val
  val="$(value "${key}")"
  if [[ "${val}" == https://* ]]; then
    pass "${key}" "https"
  else
    blocker "${key}" "must start with https://"
  fi
}

if [[ ! -f "${ENV_FILE}" ]]; then
  blocker "env.file" "not found: ${ENV_FILE}"
  echo "SUMMARY blockers=${BLOCKERS}"
  exit 1
fi

read_env_file "${ENV_FILE}"

echo "=== PRODUCTION ENV VALIDATION ==="
echo "Env file: ${ENV_FILE}"

for key in \
  APP_ENV \
  SPREADSHEET_ID \
  INTAKE_SPREADSHEET_ID \
  INTAKE_TAB_NAME \
  SESSION_SECRET \
  SESSION_COOKIE_SECURE \
  ALLOW_LEGACY_STAFF_LOGIN \
  AUTH_DEBUG_CODE_IN_RESPONSE \
  ALLOW_MANUAL_OTP_DELIVERY \
  OTP_DELIVERY_WEBHOOK_URL \
  OTP_DELIVERY_WEBHOOK_TOKEN \
  CORS_ALLOW_ORIGINS \
  AGENTS_SECRET \
  PUBLIC_CLUB_ID; do
  require_value "${key}"
  block_placeholder "${key}"
done

require_exact APP_ENV production
require_exact SESSION_COOKIE_SECURE true
require_exact ALLOW_LEGACY_STAFF_LOGIN false
require_exact AUTH_DEBUG_CODE_IN_RESPONSE false
require_exact ALLOW_MANUAL_OTP_DELIVERY false
require_https OTP_DELIVERY_WEBHOOK_URL

CORS="$(value CORS_ALLOW_ORIGINS)"
if [[ "${CORS}" =~ localhost|127\.0\.0\.1|http:// ]]; then
  blocker CORS_ALLOW_ORIGINS "production origins must be HTTPS public origins, not localhost/http"
else
  pass CORS_ALLOW_ORIGINS "no localhost/http origins"
fi

if [[ "$(value SESSION_SECRET | wc -c)" -le 32 ]]; then
  blocker SESSION_SECRET "must be at least 32 characters"
else
  pass SESSION_SECRET.length ">= 32"
fi

if [[ "$(value AGENTS_SECRET | wc -c)" -le 24 ]]; then
  blocker AGENTS_SECRET "must be at least 24 characters"
else
  pass AGENTS_SECRET.length ">= 24"
fi

credential_count=0
for key in GOOGLE_SERVICE_ACCOUNT_JSON GOOGLE_SERVICE_ACCOUNT_JSON_INLINE GOOGLE_SERVICE_ACCOUNT_JSON_BASE64; do
  if [[ -n "$(value "${key}")" ]]; then
    credential_count=$((credential_count + 1))
  fi
done

if [[ "${credential_count}" -eq 1 ]]; then
  pass google.credentials "exactly one credentials option configured"
else
  blocker google.credentials "configure exactly one credentials option; found ${credential_count}"
fi

echo "SUMMARY blockers=${BLOCKERS}"
if [[ "${BLOCKERS}" -gt 0 ]]; then
  exit 1
fi
