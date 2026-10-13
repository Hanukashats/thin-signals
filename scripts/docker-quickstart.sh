#!/usr/bin/env bash
# Reproducible local deployment. Secrets are generated/read locally and never printed.
set -euo pipefail

ACTION="${1:-up}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SECRETS_DIR="${TS_SECRETS_DIR:-$ROOT/.secrets}"
UPSTREAM_ROOT="${TS_UPSTREAM_ROOT:-$ROOT/.cache/upstreams}"
GPTR_DIR="$UPSTREAM_ROOT/gpt-researcher-v3.7.0"
GPTR_REPO="https://github.com/assafelovic/gpt-researcher.git"
GPTR_TAG="v3.7.0"
GPTR_SHA="0957c301ed06c2a5857b834358c7227c739041d4"
GPTR_IMAGE="thin-signals/gpt-researcher:3.7.0-0957c301"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-thin-signals}"
COMPOSE=(docker compose --project-name "$PROJECT_NAME" -f "$ROOT/compose.quickstart.yaml")

export TS_SECRETS_DIR="$SECRETS_DIR"

log() { printf '\n== %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 2; }

require_commands() {
  local command
  for command in docker git openssl python3; do
    command -v "$command" >/dev/null || die "missing command: $command"
  done
  docker compose version >/dev/null
}

write_private_file() {
  local destination="$1" value="$2" temporary
  temporary="$(mktemp "$SECRETS_DIR/.secret.XXXXXX")"
  chmod 0600 "$temporary"
  printf '%s\n' "$value" >"$temporary"
  mv -f "$temporary" "$destination"
}

read_hidden() {
  local prompt="$1" variable="$2" value
  [[ -r /dev/tty ]] || die "$variable must be supplied in a non-interactive shell"
  read -r -s -p "$prompt: " value </dev/tty
  printf '\n' >/dev/tty
  printf -v "$variable" '%s' "$value"
}

prepare_secrets() {
  local pg_password openrouter_key admin_password admin_name password_hash searx_secret
  install -d -m 0700 "$SECRETS_DIR"

  if [[ ! -s "$SECRETS_DIR/pg_password" ]]; then
    pg_password="$(openssl rand -hex 32)"
    write_private_file "$SECRETS_DIR/pg_password" "$pg_password"
    unset pg_password
  fi

  if [[ ! -s "$SECRETS_DIR/openrouter_key" ]]; then
    openrouter_key="${TS_OPENROUTER_KEY:-}"
    [[ -n "$openrouter_key" ]] || read_hidden "OpenRouter API key" openrouter_key
    ((${#openrouter_key} >= 20)) || die "OpenRouter key is unexpectedly short"
    write_private_file "$SECRETS_DIR/openrouter_key" "$openrouter_key"
    unset openrouter_key
  fi

  if [[ ! -s "$SECRETS_DIR/accounts.yaml" ]]; then
    admin_name="${TS_ADMIN_NAME:-admin}"
    [[ "$admin_name" =~ ^[A-Za-z0-9_.-]+$ ]] || die "invalid TS_ADMIN_NAME"
    admin_password="${TS_ADMIN_PASSWORD:-}"
    [[ -n "$admin_password" ]] || read_hidden "Initial UI password for $admin_name" admin_password
    ((${#admin_password} >= 12)) || die "initial UI password must have at least 12 characters"
    password_hash="$(python3 -c '
import hashlib, os
password = os.fdopen(3).read().rstrip("\n")
salt = os.urandom(16)
digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
print(f"scrypt${salt.hex()}${digest.hex()}")
' 3<<<"$admin_password")"
    write_private_file "$SECRETS_DIR/accounts.yaml" "users:
  $admin_name:
    role: admin
    password_hash: \"$password_hash\""
    unset admin_password password_hash
  fi

  if [[ ! -s "$SECRETS_DIR/searxng.env" ]]; then
    searx_secret="$(openssl rand -hex 32)"
    write_private_file "$SECRETS_DIR/searxng.env" "SEARXNG_SECRET=$searx_secret"
    unset searx_secret
  fi

  chmod 0600 \
    "$SECRETS_DIR/pg_password" \
    "$SECRETS_DIR/openrouter_key" \
    "$SECRETS_DIR/accounts.yaml" \
    "$SECRETS_DIR/searxng.env"
}

prepare_upstream() {
  install -d -m 0755 "$UPSTREAM_ROOT"
  if [[ ! -d "$GPTR_DIR/.git" ]]; then
    git clone --filter=blob:none --depth 1 --branch "$GPTR_TAG" "$GPTR_REPO" "$GPTR_DIR"
  else
    [[ "$(git -C "$GPTR_DIR" remote get-url origin)" == "$GPTR_REPO" ]] \
      || die "unexpected GPT Researcher origin"
    [[ -z "$(git -C "$GPTR_DIR" status --porcelain)" ]] \
      || die "GPT Researcher cache is dirty"
    git -C "$GPTR_DIR" fetch --force --depth 1 origin \
      "refs/tags/$GPTR_TAG:refs/tags/$GPTR_TAG"
  fi
  [[ "$(git -C "$GPTR_DIR" rev-list -n 1 "$GPTR_TAG^{commit}")" == "$GPTR_SHA" ]] \
    || die "GPT Researcher tag does not match the audited commit"
  git -C "$GPTR_DIR" checkout --detach --force "$GPTR_SHA"
  [[ -z "$(git -C "$GPTR_DIR" status --porcelain)" ]] \
    || die "GPT Researcher checkout is dirty"
}

build_images() {
  local installed_revision
  prepare_upstream
  installed_revision="$(docker image inspect "$GPTR_IMAGE" \
    --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' 2>/dev/null || true)"
  if [[ "$installed_revision" != "$GPTR_SHA" ]]; then
    log "build audited GPT Researcher $GPTR_TAG"
    docker build --pull \
      --label "org.opencontainers.image.source=$GPTR_REPO" \
      --label "org.opencontainers.image.version=$GPTR_TAG" \
      --label "org.opencontainers.image.revision=$GPTR_SHA" \
      --tag "$GPTR_IMAGE" "$GPTR_DIR"
  fi
  log "build Thin Signals application image"
  "${COMPOSE[@]}" build --pull api
}

case "$ACTION" in
  prepare)
    require_commands
    prepare_secrets
    log "private secret files prepared in $SECRETS_DIR"
    ;;
  config)
    require_commands
    prepare_secrets
    "${COMPOSE[@]}" config --quiet
    log "Compose configuration is valid"
    ;;
  build)
    require_commands
    prepare_secrets
    build_images
    ;;
  up)
    require_commands
    prepare_secrets
    build_images
    "${COMPOSE[@]}" up -d --remove-orphans --wait --wait-timeout 600
    printf '\nUI:  http://127.0.0.1:%s\nAPI: http://127.0.0.1:%s/ready\n' \
      "${TS_UI_PORT:-8501}" "${TS_API_PORT:-8095}"
    ;;
  status)
    require_commands
    "${COMPOSE[@]}" ps
    ;;
  logs)
    require_commands
    "${COMPOSE[@]}" logs --tail 200
    ;;
  down)
    require_commands
    "${COMPOSE[@]}" down --remove-orphans
    log "containers stopped; named volumes and all data were preserved"
    ;;
  *)
    die "usage: $0 [prepare|config|build|up|status|logs|down]"
    ;;
esac
