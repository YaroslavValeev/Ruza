#!/usr/bin/env bash
# Deploy / restart API container on Linux VPS
# Usage: bash scripts/server/deploy-api.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env.docker"
IMAGE="icebeach-api:latest"
NAME="icebeach-api"

bash "${REPO_ROOT}/scripts/server/assert-clean-release-tree.sh"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy from .env.docker.example"
  exit 1
fi

bash "${REPO_ROOT}/scripts/server/validate-production-env.sh" "${ENV_FILE}"

cd "${REPO_ROOT}/icebeach-wakeclub"
docker build -t "${IMAGE}" .

docker stop "${NAME}" 2>/dev/null || true
docker rm "${NAME}" 2>/dev/null || true

docker run -d \
  --name "${NAME}" \
  --restart unless-stopped \
  --env-file "${ENV_FILE}" \
  -p 127.0.0.1:8000:8000 \
  "${IMAGE}"

sleep 3
curl -fsS "http://127.0.0.1:8000/health"
echo ""
echo "API deployed: ${NAME}"
