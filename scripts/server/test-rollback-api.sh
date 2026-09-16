#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

ROLLBACK_SCRIPT="${REPO_ROOT}/scripts/server/rollback-api.sh"
TEST_REPO="${TMP_DIR}/repo"
mkdir -p "${TEST_REPO}"
cd "${TEST_REPO}"

git init -q
git config user.email "ci@example.test"
git config user.name "CI"

echo "v1" > app.txt
git add app.txt
git commit -q -m "v1"
git tag v1.0.0-rc.1
V1_SHA="$(git rev-parse --verify HEAD)"

echo "v2" > app.txt
git commit -q -am "v2"
git tag v1.0.0-rc.2
V2_SHA="$(git rev-parse --verify HEAD)"

DRY_OUTPUT="$(bash "${ROLLBACK_SCRIPT}" --repo-root "${TEST_REPO}" --target-tag v1.0.0-rc.1)"
echo "${DRY_OUTPUT}"
if [[ "${DRY_OUTPUT}" != *"ROLLBACK_PLAN_OK target=v1.0.0-rc.1"* ]]; then
  echo "[BLOCKER] rollback dry-run did not report plan ok"
  exit 1
fi
if [[ "$(git rev-parse --verify HEAD)" != "${V2_SHA}" ]]; then
  echo "[BLOCKER] rollback dry-run changed HEAD"
  exit 1
fi

echo "dirty" >> app.txt
set +e
DIRTY_OUTPUT="$(bash "${ROLLBACK_SCRIPT}" --repo-root "${TEST_REPO}" --target-tag v1.0.0-rc.1 2>&1)"
DIRTY_STATUS=$?
set -e
echo "${DIRTY_OUTPUT}"
if [[ "${DIRTY_STATUS}" -eq 0 || "${DIRTY_OUTPUT}" != *"[BLOCKER] rollback.clean"* ]]; then
  echo "[BLOCKER] rollback did not block dirty working tree"
  exit 1
fi

git checkout -- app.txt
DEPLOY_LOG="${TMP_DIR}/deploy.log"
HEALTH_LOG="${TMP_DIR}/health.log"
EXEC_OUTPUT="$(
  bash "${ROLLBACK_SCRIPT}" \
    --repo-root "${TEST_REPO}" \
    --target-tag v1.0.0-rc.1 \
    --deploy-command "echo deploy >> '${DEPLOY_LOG}'" \
    --healthcheck-command "echo health >> '${HEALTH_LOG}'" \
    --execute
)"
echo "${EXEC_OUTPUT}"

if [[ "$(git rev-parse --verify HEAD)" != "${V1_SHA}" ]]; then
  echo "[BLOCKER] rollback execute did not checkout target tag"
  exit 1
fi
if [[ "$(cat "${DEPLOY_LOG}")" != "deploy" || "$(cat "${HEALTH_LOG}")" != "health" ]]; then
  echo "[BLOCKER] rollback execute did not run deploy and healthcheck commands"
  exit 1
fi
if [[ "${EXEC_OUTPUT}" != *"ROLLBACK_OK target=v1.0.0-rc.1"* ]]; then
  echo "[BLOCKER] rollback execute did not report success"
  exit 1
fi

echo "[PASS] rollback behavior verified"
