# ADR-010 — Local research contour on VM232

Status: **implemented and self-tested; independent acceptance pending**
Date: 2026-10-12
Decision class: major operational boundary change

## Context

After the home storage failure, Thin Signals was restored on VM232 but its
declared SearXNG endpoint had no local service. Reusing VM101 would restore
functionality but would keep the product dependent on the general AGI backend.
The operator requested a self-contained research contour on the Thin Signals
server.

## Decision

Run two upstream-native containers on VM232:

1. SearXNG, consumed by both the existing Thin Signals connector and GPT
   Researcher.
2. GPT Researcher, used as an optional deep-research adapter and never as a
   source of final truth.

Both services bind only to loopback. VM232's host sing-box remains the single
egress TUN for host and container traffic. No application-level proxy and no
VM101/OpenWrt service hop is introduced.

The Thin Signals API points to `http://127.0.0.1:28088`; GPT Researcher reaches
SearXNG through Docker DNS. GPT Researcher is on `127.0.0.1:28000`. Neither is
published through Caddy.

## Pinned upstreams

| Component | Pin | License | Native interface |
|---|---|---|---|
| SearXNG | image version `2026.9.18-12df7aed6`, amd64 digest `sha256:31e3ca5e206ef71b148773e196cc575dc9c866d4f5047c8a7038a45c38bd4578` | AGPL-3.0-or-later | `GET /search?q=...&format=json` |
| GPT Researcher | tag `v3.7.0`, commit `0957c301ed06c2a5857b834358c7227c739041d4` | Apache-2.0 repository license | FastAPI HTTP + `/ws` |

The mutable Docker Hub GPT Researcher image is rejected because inspection
showed package 0.12.8 built in March 2025. The exact release source is built
locally and the resulting image ID is recorded in deployment evidence.

## Security and data boundary

- Loopback-only host ports and no public proxy route.
- Non-root upstream GPT Researcher user, dropped capabilities and
  `no-new-privileges`.
- OpenRouter key is a mounted Docker secret, never Compose environment or Git.
- ZDR and `data_collection=deny` are supplied for LLM calls.
- Bounded result count, iterations, concurrency, output tokens and resources.
- Web pages and generated reports are untrusted data. GPT Researcher reports
  may propose URLs; the product accepts only directly fetched and validated
  fragments into its evidence ledger.

## Persistence, health and rollback

SearXNG cache and GPT Researcher reports/outputs live under
`/srv/thin-signals-research`. Containers use `restart: unless-stopped`; an
enabled `thin-signals-research.service` recreates the exact Compose project at
boot. Health probes are local HTTP requests.

Rollback disables/stops that unit, removes its containers without deleting
the `/srv` data, restores the API drop-in with an empty SearXNG URL, and
restarts only `thin-signals-api`. PostgreSQL is not changed.

## Verification

The deployment and reboot evidence is recorded in
`reports/VM232_RESEARCH_2026-10-12.md`. A real GPT Researcher query and a real
Thin Signals candidate run completed; controlled service restart and full VM
reboot recovered without intervention. All research ports remained loopback
only. This is implementation evidence, not independent acceptance.

## Consequences

The restored product no longer depends on VM101 for web metasearch or deep
research. It still depends on public search engines and direct OpenRouter; the
word “local” describes service ownership, not fully offline inference.
