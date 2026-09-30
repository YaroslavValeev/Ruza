#!/usr/bin/env bash
# Ruza bootstrap for an already approved MyWave deployment target.
# Usage after architecture approval:
#   MYWAVE_SERVER_ID=S1 RUZA_ROOT=/approved/canonical/folder \
#   RUZA_BOOTSTRAP_APPROVED=true bash scripts/server/bootstrap-ubuntu.sh
set -euo pipefail

if [[ "${RUZA_BOOTSTRAP_APPROVED:-}" != "true" ]]; then
  echo "Blocked: set RUZA_BOOTSTRAP_APPROVED=true only after the deployment card is approved."
  exit 1
fi

if [[ -z "${MYWAVE_SERVER_ID:-}" ]]; then
  echo "Blocked: set MYWAVE_SERVER_ID to the approved canonical server ID."
  exit 1
fi

if [[ "${MYWAVE_SERVER_ID}" == "S3" ]]; then
  echo "Blocked: S3 is Shared EU / LLM / Proxy infrastructure, not an application host."
  exit 1
fi

if [[ -z "${RUZA_ROOT:-}" || "${RUZA_ROOT}" != /* || "${RUZA_ROOT}" == *approved/canonical/folder* ]]; then
  echo "Blocked: set RUZA_ROOT to the approved absolute canonical folder."
  echo "See docs/MYWAVE_INFRASTRUCTURE.md; Ruza placement is currently NOT DEPLOYED/TBD."
  exit 1
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

apt update
apt install -y ca-certificates curl git ufw openssl

if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" > /etc/apt/sources.list.d/docker.list
  apt update
  apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

mkdir -p "${RUZA_ROOT}"
echo "Bootstrap done. Next:"
echo "  cd ${RUZA_ROOT} && git clone <your-repo-url> ."
echo "  cp .env.docker.example .env.docker && nano .env.docker"
echo "  See docs/SERVER_COMMANDS.md section 3.4"
