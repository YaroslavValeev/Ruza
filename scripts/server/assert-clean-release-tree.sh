#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "${REPO_ROOT}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Deploy blocked: ${REPO_ROOT} is not a git work tree"
  exit 1
fi

if [[ -n "$(git status --porcelain=v1)" ]]; then
  echo "Deploy blocked: working tree is dirty. Commit, stash, or discard local changes before production deploy."
  git status --short
  exit 1
fi

SHA="$(git rev-parse --verify HEAD)"
echo "Release tree clean: ${SHA}"
