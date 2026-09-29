#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET_TAG=""
DEPLOY_COMMAND="bash scripts/server/deploy-api.sh"
HEALTHCHECK_COMMAND=""
EXECUTE=0

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/server/rollback-api.sh --target-tag v1.0.0-rc.N [options]

Options:
  --repo-root PATH          Repository root, default: auto-detected project root.
  --deploy-command COMMAND  Command to deploy after checkout, default: bash scripts/server/deploy-api.sh.
  --healthcheck-command CMD Optional command to run after deploy.
  --execute                 Actually checkout target tag and run deploy. Without this, only validates and prints plan.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      REPO_ROOT="${2:-}"
      shift 2
      ;;
    --target-tag)
      TARGET_TAG="${2:-}"
      shift 2
      ;;
    --deploy-command)
      DEPLOY_COMMAND="${2:-}"
      shift 2
      ;;
    --healthcheck-command)
      HEALTHCHECK_COMMAND="${2:-}"
      shift 2
      ;;
    --execute)
      EXECUTE=1
      shift
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

if [[ -z "${TARGET_TAG}" ]]; then
  echo "--target-tag is required" >&2
  usage >&2
  exit 2
fi

cd "${REPO_ROOT}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[BLOCKER] rollback.repo: ${REPO_ROOT} is not a git work tree"
  exit 1
fi

if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "[BLOCKER] rollback.clean: working tree is dirty"
  git status --short
  exit 1
fi

CURRENT_SHA="$(git rev-parse --verify HEAD)"
TARGET_SHA="$(git rev-parse --verify "${TARGET_TAG}^{commit}" 2>/dev/null || true)"
if [[ -z "${TARGET_SHA}" ]]; then
  echo "[BLOCKER] rollback.target: tag/ref not found: ${TARGET_TAG}"
  exit 1
fi

echo "=== RUZA API ROLLBACK ==="
echo "Repo: ${REPO_ROOT}"
echo "Current: ${CURRENT_SHA}"
echo "Target: ${TARGET_TAG} ${TARGET_SHA}"
echo "Deploy command: ${DEPLOY_COMMAND}"
if [[ -n "${HEALTHCHECK_COMMAND}" ]]; then
  echo "Healthcheck command: ${HEALTHCHECK_COMMAND}"
fi

if [[ "${EXECUTE}" -ne 1 ]]; then
  echo "DRY_RUN only. Add --execute to checkout target tag and deploy."
  echo "ROLLBACK_PLAN_OK target=${TARGET_TAG}"
  exit 0
fi

git checkout --force "${TARGET_TAG}"
echo "Checked out $(git rev-parse --verify HEAD)"

bash -lc "${DEPLOY_COMMAND}"

if [[ -n "${HEALTHCHECK_COMMAND}" ]]; then
  bash -lc "${HEALTHCHECK_COMMAND}"
fi

echo "ROLLBACK_OK target=${TARGET_TAG}"
