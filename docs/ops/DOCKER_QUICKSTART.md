# Docker quick deploy

This package starts the complete Thin Signals runtime without backend VM101:

- PostgreSQL 16 + pgvector and an isolated migration job;
- Thin Signals API and Russian Streamlit UI;
- pinned SearXNG and GPT Researcher search contour.

All published ports bind to `127.0.0.1` by default. Put an existing TLS reverse
proxy in front of the UI/API when public access is required. The compose file
does not publish a database, dashboard, or model credential to the internet.

## Requirements

- Linux host with Docker Engine and Docker Compose v2;
- `git`, `openssl`, and Python 3 on the host;
- 8 GB RAM minimum, 12 GB recommended; 4 CPU cores and 120 GB disk recommended;
- an OpenRouter API key.

## First start

```bash
git clone --branch feat/thin-signals-reliability-20261012 --single-branch \
  https://git.sourcecraft.dev/shats123/thin-signals.git
cd thin-signals
scripts/docker-quickstart.sh up
```

The same named branch is mirrored publicly at
`https://github.com/Hanukashats/thin-signals`. The historical `main` branch is
retained without rewritten commits, so a default-branch clone is not the 7.8
reliability release.

The script asks once for the OpenRouter key and an initial UI administrator
password. It creates only mode-`0600` files under `.secrets/`, builds GPT
Researcher from audited tag `v3.7.0` / commit `0957c301`, builds the application
from the pinned Python base and exact dependency lock, applies migrations, and
waits for every service to become healthy.

Open:

- UI: `http://127.0.0.1:8501`
- API readiness: `http://127.0.0.1:8095/ready`
- SearXNG: `http://127.0.0.1:28088`
- GPT Researcher: `http://127.0.0.1:28000`

Override a loopback port with `TS_UI_PORT`, `TS_API_PORT`, `TS_PG_PORT`,
`TS_SEARXNG_PORT`, or `TS_GPTR_PORT`. Changing `TS_BIND_HOST` away from
`127.0.0.1` is an explicit exposure decision and should be protected by a host
firewall and authentication.

## Configuration and secrets

Non-secret defaults are versioned in `deploy/docker/runtime.env.example`.
To customize them without changing Git:

```bash
cp deploy/docker/runtime.env.example .secrets/runtime.env
TS_RUNTIME_ENV_FILE=.secrets/runtime.env scripts/docker-quickstart.sh up
```

The adversarial researcher/critic/defender/control round is deliberately off in
the example. Enable `TS_ADVERSARIAL_REVIEW_ENABLED=true` only after the frozen
evaluation and a bounded live canary pass for the chosen model routes. GPT
Researcher is enabled by default, but its prose is never accepted directly:
Thin Signals extracts bounded public URLs and refetches them through its normal
evidence path.

Secret files are never part of the image or Git tree:

| File | Purpose |
|---|---|
| `.secrets/pg_password` | PostgreSQL password |
| `.secrets/openrouter_key` | shared OpenRouter key for the app and GPT Researcher |
| `.secrets/accounts.yaml` | scrypt UI account hashes |
| `.secrets/searxng.env` | private SearXNG instance key |

For automation, provide `TS_OPENROUTER_KEY`, `TS_ADMIN_NAME`, and
`TS_ADMIN_PASSWORD` only to the `prepare`/`up` process. They are written to the
private files and are not printed. `TS_SECRETS_DIR` may point to an external
host-only directory.

## Operations

```bash
scripts/docker-quickstart.sh status
scripts/docker-quickstart.sh logs
scripts/docker-quickstart.sh down     # keeps every named volume
scripts/docker-quickstart.sh up       # idempotent rebuild/start
```

Before an upgrade, back up the database and record the current Git SHA:

```bash
docker compose -f compose.quickstart.yaml exec -T pg \
  pg_dump -Fc -U ts -d thin_signals > thin-signals.dump
git rev-parse HEAD
```

Validate the archive before relying on it:

```bash
docker compose -f compose.quickstart.yaml exec -T pg \
  pg_restore -l < thin-signals.dump >/dev/null
sha256sum thin-signals.dump
```

Rollback is: disable the new feature flag, return to the recorded Git SHA,
rebuild, run migrations compatible with that release, and restore the archive
only if a data rollback is actually required. The helper intentionally has no
volume-deletion action.

## Supply-chain pins

- application base: Python `3.14.4-slim-bookworm` by image digest;
- PostgreSQL/pgvector and SearXNG by image digest;
- GPT Researcher source by exact Git commit and locally labelled image;
- Python runtime packages by exact version in `deploy/docker/requirements.lock`.

Re-pin one module at a time, then repeat unit, migration, container health and
live-canary gates before publication.
