#!/usr/bin/env bash
# Bootstrap an Ubuntu 24.04 Thin Signals VM on the home Proxmox host.
# Idempotent: safe to re-run as a sudo-capable cloud-init user.
#
# VM230 compatibility:
#   VM_HOSTNAME=agi-thin-signals EXPOSE_DEMO_PORTS=1 \
#     ENABLE_SING_BOX_REDIRECT=1 bash scripts/vm230-bootstrap.sh
#
# VM231 private staging:
#   VM_HOSTNAME=agi-thin-signals-v2 bash scripts/vm230-bootstrap.sh
set -euo pipefail

AGENT_USER="${AGENT_USER:-agent}"
VM_HOSTNAME="${VM_HOSTNAME:-$(hostname)}"
PROJECT_DIR="${PROJECT_DIR:-/opt/thin-signals}"
ARCHIVE_DIR="${ARCHIVE_DIR:-/opt/thin-signals-archive}"
INSTALL_NETBIRD="${INSTALL_NETBIRD:-1}"
EXPOSE_DEMO_PORTS="${EXPOSE_DEMO_PORTS:-0}"
ENABLE_SING_BOX_REDIRECT="${ENABLE_SING_BOX_REDIRECT:-0}"
SSH_CIDRS="${SSH_CIDRS:-192.168.5.0/24 10.66.78.0/24 10.200.200.0/24}"
CURRENT_USER="${SUDO_USER:-$(id -un)}"
export DEBIAN_FRONTEND=noninteractive

log() { printf '\n== %s\n' "$*"; }

require_flag() {
  local name="$1" value="$2"
  if [[ "$value" != "0" && "$value" != "1" ]]; then
    printf 'error: %s must be 0 or 1\n' "$name" >&2
    exit 2
  fi
}

require_flag INSTALL_NETBIRD "$INSTALL_NETBIRD"
require_flag EXPOSE_DEMO_PORTS "$EXPOSE_DEMO_PORTS"
require_flag ENABLE_SING_BOX_REDIRECT "$ENABLE_SING_BOX_REDIRECT"

log "hostname / timezone"
sudo hostnamectl set-hostname "$VM_HOSTNAME"
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
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  version_codename="$(sed -n 's/^VERSION_CODENAME=//p' /etc/os-release | tr -d '"')"
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu %s stable\n' \
    "$(dpkg --print-architecture)" "$version_codename" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo systemctl enable --now docker

if [[ "$INSTALL_NETBIRD" == "1" ]]; then
  log "netbird (official repo)"
  if ! command -v netbird >/dev/null; then
    curl -fsSL https://pkgs.netbird.io/debian/public.key \
      | sudo gpg --dearmor --yes -o /usr/share/keyrings/netbird-archive-keyring.gpg
    printf '%s\n' \
      'deb [signed-by=/usr/share/keyrings/netbird-archive-keyring.gpg] https://pkgs.netbird.io/debian stable main' \
      | sudo tee /etc/apt/sources.list.d/netbird.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq netbird
  fi
fi

log "agent user"
if ! id "$AGENT_USER" >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash -G sudo,docker "$AGENT_USER"
fi
sudo usermod -aG sudo,docker "$AGENT_USER"
if id "$CURRENT_USER" >/dev/null 2>&1; then
  sudo usermod -aG docker "$CURRENT_USER"
fi
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$AGENT_USER" \
  | sudo tee "/etc/sudoers.d/90-$AGENT_USER" >/dev/null
sudo chmod 440 "/etc/sudoers.d/90-$AGENT_USER"

agent_home="$(getent passwd "$AGENT_USER" | cut -d: -f6)"
current_home="$(getent passwd "$CURRENT_USER" | cut -d: -f6)"
source_keys="$current_home/.ssh/authorized_keys"
target_keys="$agent_home/.ssh/authorized_keys"
sudo install -d -m 700 -o "$AGENT_USER" -g "$AGENT_USER" "$agent_home/.ssh"
if [[ "$source_keys" != "$target_keys" ]]; then
  if [[ ! -s "$source_keys" ]]; then
    printf 'error: no authorized keys at %s\n' "$source_keys" >&2
    exit 3
  fi
  sudo install -m 600 -o "$AGENT_USER" -g "$AGENT_USER" "$source_keys" "$target_keys"
else
  sudo chown "$AGENT_USER:$AGENT_USER" "$target_keys"
  sudo chmod 600 "$target_keys"
fi

log "project dirs"
sudo install -d -o "$AGENT_USER" -g "$AGENT_USER" "$PROJECT_DIR" "$ARCHIVE_DIR"

log "ufw: private management only"
sudo ufw --force reset >/dev/null
sudo ufw default deny incoming
sudo ufw default allow outgoing
read -r -a ssh_cidrs <<<"$SSH_CIDRS"
for cidr in "${ssh_cidrs[@]}"; do
  sudo ufw allow from "$cidr" to any port 22 proto tcp
done
if [[ "$EXPOSE_DEMO_PORTS" == "1" ]]; then
  for cidr in "${ssh_cidrs[@]}"; do
    sudo ufw allow from "$cidr" to any port 8501 proto tcp comment 'streamlit private demo'
    sudo ufw allow from "$cidr" to any port 8000 proto tcp comment 'fastapi private demo'
  done
fi
if [[ "$ENABLE_SING_BOX_REDIRECT" == "1" ]]; then
  # sing-box auto_redirect sends container traffic to a host listener.
  sudo ufw allow from 172.16.0.0/12 comment 'docker bridges to sing-box host listener'
fi
sudo ufw --force enable

log "unattended security upgrades"
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

log "sshd hardening"
sudo install -d -m 755 /etc/ssh/sshd_config.d
printf '%s\n' \
  'PasswordAuthentication no' \
  'KbdInteractiveAuthentication no' \
  'PermitRootLogin prohibit-password' \
  | sudo tee /etc/ssh/sshd_config.d/99-thin-signals.conf >/dev/null
sudo sshd -t
sudo systemctl reload ssh

log "done"
sudo docker --version
sudo docker compose version
if command -v netbird >/dev/null; then netbird version; fi
python3 --version
git --version
