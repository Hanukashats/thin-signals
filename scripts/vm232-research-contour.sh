#!/usr/bin/env bash
# Build and deploy the private VM232 SearXNG + GPT Researcher contour.
# Usage: scripts/vm232-research-contour.sh [install|status|rollback]
set -euo pipefail

ACTION="${1:-install}"
PROJECT_DIR="${PROJECT_DIR:-/opt/thin-signals}"
UPSTREAM_ROOT="${UPSTREAM_ROOT:-/opt/upstreams}"
GPTR_DIR="$UPSTREAM_ROOT/gpt-researcher-v3.7.0"
GPTR_REPO="https://github.com/assafelovic/gpt-researcher.git"
GPTR_TAG="v3.7.0"
GPTR_SHA="0957c301ed06c2a5857b834358c7227c739041d4"
GPTR_IMAGE="thin-signals/gpt-researcher:3.7.0-0957c301"
SEARX_IMAGE="searxng/searxng@sha256:31e3ca5e206ef71b148773e196cc575dc9c866d4f5047c8a7038a45c38bd4578"
COMPOSE_FILE="$PROJECT_DIR/deploy/research/compose.yaml"
UNIT_FILE="$PROJECT_DIR/deploy/systemd/thin-signals-research.service"
API_DROPIN="$PROJECT_DIR/deploy/systemd/thin-signals-api-home-vm.conf"
API_ROLLBACK="$PROJECT_DIR/deploy/systemd/thin-signals-api-home-vm-no-research.conf"
SEARX_ENV="/etc/thin-signals-research/searxng.env"

log() { printf '\n== %s\n' "$*"; }

wait_http() {
  local url="$1" tries="${2:-60}"
  local i
  for i in $(seq 1 "$tries"); do
    if curl -fsS --max-time 8 "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  printf 'error: timed out waiting for %s\n' "$url" >&2
  return 1
}

status() {
  sudo systemctl --no-pager --full status thin-signals-research.service || true
  sudo docker compose --project-name thin-signals-research -f "$COMPOSE_FILE" ps
  curl -fsS --max-time 8 'http://127.0.0.1:28088/search?q=health&format=json' \
    | jq '{results: (.results | length)}'
  curl -fsS --max-time 8 'http://127.0.0.1:28000/.well-known/agent-discovery.json' \
    | jq '{name, url, version}'
}

rollback() {
  log "disable local research services"
  sudo systemctl disable --now thin-signals-research.service
  sudo install -m 0644 "$API_ROLLBACK" \
    /etc/systemd/system/thin-signals-api.service.d/10-home-vm.conf
  sudo systemctl daemon-reload
  sudo systemctl restart thin-signals-api.service
  wait_http 'http://127.0.0.1:8095/ready' 30
  log "rollback complete; persistent research data and images were preserved"
}

install_contour() {
  for command in curl docker git jq openssl; do
    command -v "$command" >/dev/null || {
      printf 'error: missing command %s\n' "$command" >&2
      exit 2
    }
  done
  [[ -f "$COMPOSE_FILE" && -f "$UNIT_FILE" && -f "$API_DROPIN" ]] || {
    printf 'error: run from a checkout containing the VM232 research deployment files\n' >&2
    exit 2
  }

  log "prepare host-only state"
  sudo install -d -m 0755 -o "$(id -un)" -g "$(id -gn)" "$UPSTREAM_ROOT"
  sudo install -d -m 0700 /etc/thin-signals-research
  sudo install -d -m 0750 -o 1000 -g 1000 \
    /srv/thin-signals-research/data \
    /srv/thin-signals-research/logs \
    /srv/thin-signals-research/my-docs \
    /srv/thin-signals-research/outputs \
    /srv/thin-signals-research/searxng-cache
  if ! sudo test -s "$SEARX_ENV"; then
    local searx_secret
    searx_secret="$(openssl rand -hex 32)"
    printf 'SEARXNG_SECRET=%s\n' "$searx_secret" \
      | sudo tee "$SEARX_ENV" >/dev/null
    unset searx_secret
    sudo chmod 0600 "$SEARX_ENV"
  fi

  log "verify and build official GPT Researcher $GPTR_TAG"
  if [[ ! -d "$GPTR_DIR/.git" ]]; then
    git clone --filter=blob:none --no-checkout "$GPTR_REPO" "$GPTR_DIR"
  fi
  [[ "$(git -C "$GPTR_DIR" remote get-url origin)" == "$GPTR_REPO" ]] || {
    printf 'error: unexpected GPT Researcher origin\n' >&2
    exit 3
  }
  git -C "$GPTR_DIR" fetch --force --depth 1 origin \
    "refs/tags/$GPTR_TAG:refs/tags/$GPTR_TAG"
  [[ "$(git -C "$GPTR_DIR" rev-list -n 1 "$GPTR_TAG^{commit}")" == "$GPTR_SHA" ]] || {
    printf 'error: GPT Researcher tag does not resolve to the audited commit\n' >&2
    exit 3
  }
  git -C "$GPTR_DIR" checkout --detach --force "$GPTR_SHA"
  [[ -z "$(git -C "$GPTR_DIR" status --porcelain)" ]] || {
    printf 'error: GPT Researcher source checkout is dirty\n' >&2
    exit 3
  }
  docker build --pull \
    --label "org.opencontainers.image.source=$GPTR_REPO" \
    --label "org.opencontainers.image.version=$GPTR_TAG" \
    --label "org.opencontainers.image.revision=$GPTR_SHA" \
    --tag "$GPTR_IMAGE" "$GPTR_DIR"

  log "pull pinned SearXNG and validate Compose"
  docker pull "$SEARX_IMAGE"
  sudo docker compose --project-name thin-signals-research \
    -f "$COMPOSE_FILE" config --quiet

  log "install boot unit and start research contour"
  sudo install -m 0644 "$UNIT_FILE" /etc/systemd/system/thin-signals-research.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now thin-signals-research.service
  wait_http 'http://127.0.0.1:28088/search?q=health&format=json' 90
  wait_http 'http://127.0.0.1:28000/' 90

  log "connect Thin Signals API to local SearXNG"
  sudo install -d -m 0755 /etc/systemd/system/thin-signals-api.service.d
  sudo install -m 0644 "$API_DROPIN" \
    /etc/systemd/system/thin-signals-api.service.d/10-home-vm.conf
  sudo systemctl daemon-reload
  sudo systemctl restart thin-signals-api.service
  wait_http 'http://127.0.0.1:8095/ready' 30

  log "deployment status"
  status
  docker image inspect "$GPTR_IMAGE" \
    --format 'gpt_researcher_image={{.Id}} created={{.Created}} revision={{index .Config.Labels "org.opencontainers.image.revision"}}'
}

case "$ACTION" in
  install) install_contour ;;
  status) status ;;
  rollback) rollback ;;
  *) printf 'usage: %s [install|status|rollback]\n' "$0" >&2; exit 2 ;;
esac

