#!/usr/bin/env bash
# Bootstrap for VM 230 "agi-thin-signals" (home Proxmox, Ubuntu 24.04 cloud image).
# Idempotent: safe to re-run. Run as a sudo-capable user (cloud-init `ubuntu`).
#   ssh vm230 'bash -s' < scripts/vm230-bootstrap.sh
set -euo pipefail

AGENT_USER="${AGENT_USER:-agent}"
PROJECT_DIR="${PROJECT_DIR:-/opt/thin-signals}"
ARCHIVE_DIR="${ARCHIVE_DIR:-/opt/thin-signals-archive}"
export DEBIAN_FRONTEND=noninteractive

log() { printf '\n== %s\n' "$*"; }

log "hostname / timezone"
sudo hostnamectl set-hostname agi-thin-signals
sudo timedatectl set-timezone UTC

log "apt base"
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends \
  ca-certificates curl gnupg git rsync jq unzip p7zip-full ripgrep \
  python3-venv python3-pip python3-dev build-essential libpq-dev postgresql-client \
  qemu-guest-agent ufw unattended-upgrades htop
sudo systemctl enable --now qemu-guest-agent

log "docker (official repo)"
if ! command -v docker >/dev/null; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo systemctl enable --now docker

log "netbird (official repo)"
if ! command -v netbird >/dev/null; then
  curl -fsSL https://pkgs.netbird.io/debian/public.key | sudo gpg --dearmor -o /usr/share/keyrings/netbird-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/netbird-archive-keyring.gpg] https://pkgs.netbird.io/debian stable main" \
    | sudo tee /etc/apt/sources.list.d/netbird.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq netbird
fi

log "agent user"
if ! id "$AGENT_USER" >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash -G sudo,docker "$AGENT_USER"
fi
sudo usermod -aG docker "$AGENT_USER"
sudo usermod -aG docker ubuntu
echo "$AGENT_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/90-$AGENT_USER >/dev/null
sudo chmod 440 /etc/sudoers.d/90-$AGENT_USER
sudo install -d -m 700 -o "$AGENT_USER" -g "$AGENT_USER" /home/$AGENT_USER/.ssh
sudo install -m 600 -o "$AGENT_USER" -g "$AGENT_USER" /home/ubuntu/.ssh/authorized_keys /home/$AGENT_USER/.ssh/authorized_keys

log "project dirs"
sudo install -d -o "$AGENT_USER" -g "$AGENT_USER" "$PROJECT_DIR" "$ARCHIVE_DIR"

log "ufw: ssh only from LAN + NetBird"
sudo ufw --force reset >/dev/null
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.5.0/24 to any port 22 proto tcp
sudo ufw allow from 10.200.200.0/24 to any port 22 proto tcp
sudo ufw allow from 192.168.5.0/24 to any port 8501 proto tcp comment 'streamlit LAN demo'
sudo ufw allow from 10.200.200.0/24 to any port 8501 proto tcp
sudo ufw allow from 192.168.5.0/24 to any port 8000 proto tcp comment 'fastapi LAN demo'
sudo ufw allow from 10.200.200.0/24 to any port 8000 proto tcp
# sing-box auto_redirect sends container traffic to a local listener -> must pass INPUT
sudo ufw allow from 172.16.0.0/12 comment 'docker bridges -> host (sing-box redirect, host services)'
sudo ufw --force enable

log "unattended security upgrades"
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

log "sshd hardening"
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh

log "done"
docker --version; docker compose version; netbird version || true; python3 --version; git --version
