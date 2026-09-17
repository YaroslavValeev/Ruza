#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GUARD="${REPO_ROOT}/scripts/server/assert-clean-release-tree.sh"
TMP_ROOT="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_ROOT}"
}
trap cleanup EXIT

echo "=== TEST CLEAN RELEASE TREE GUARD (bash) ==="
mkdir -p "${TMP_ROOT}/scripts/server"
cp "${GUARD}" "${TMP_ROOT}/scripts/server/assert-clean-release-tree.sh"
chmod +x "${TMP_ROOT}/scripts/server/assert-clean-release-tree.sh"

(
  cd "${TMP_ROOT}"
  git init >/dev/null
  git config user.email "ci@example.invalid"
  git config user.name "CI"
  echo "clean" > README.md
  git add README.md scripts
  git commit -m "initial" >/dev/null
)

bash "${TMP_ROOT}/scripts/server/assert-clean-release-tree.sh"
echo "[PASS] clean tree accepted"

echo "dirty" > "${TMP_ROOT}/dirty.txt"
if bash "${TMP_ROOT}/scripts/server/assert-clean-release-tree.sh"; then
  echo "[BLOCKER] dirty release tree was accepted"
  exit 1
fi
echo "[PASS] dirty tree blocked"
