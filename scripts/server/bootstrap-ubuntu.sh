#!/usr/bin/env bash
# Ice Beach — bootstrap Ubuntu VPS (Docker + clone placeholder)
# Usage: curl -fsSL ... | bash   OR   bash scripts/server/bootstrap-ubuntu.sh
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash $0"
  exit 1
fi

apt update && apt upgrade -y
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

mkdir -p /opt/icebeach
echo "Bootstrap done. Next:"
echo "  cd /opt/icebeach && git clone <your-repo-url> ."
echo "  cp .env.docker.example .env.docker && nano .env.docker"
echo "  See docs/SERVER_COMMANDS.md section 3.4"
