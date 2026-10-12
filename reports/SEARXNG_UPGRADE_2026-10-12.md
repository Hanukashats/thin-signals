# SearXNG one-module upgrade receipt — 2026-10-12

Status: **deployed and self-tested; independent acceptance pending**

## Change boundary

Only SearXNG changed:

| Field | Before | After |
|---|---|---|
| Tag | `2026.9.18-12df7aed6` | `2026.10.11-ad46ebd7d` |
| amd64 digest | `sha256:31e3ca5e206ef71b148773e196cc575dc9c866d4f5047c8a7038a45c38bd4578` | `sha256:00ad29bb7d72d896ac3b3ff8b252d9ad9939da3e014828934363c61dba9b7e09` |
| Upstream commit | `12df7aed60b2705c00f42d805d8d36fd43a846c2` | `ad46ebd7d87666edb5f116c5b274b47f689ac6cd` |

The candidate is 59 official upstream commits ahead and zero behind. License
remains AGPL-3.0-or-later and the consumed native interface remains
`GET /search?q=...&format=json`. GPT Researcher v3.7.0, Thin Signals code,
rules, prompts, database, public route and host sing-box were not changed.

Primary upstream evidence:

- <https://github.com/searxng/searxng/commit/ad46ebd7d87666edb5f116c5b274b47f689ac6cd>
- <https://github.com/searxng/searxng/pkgs/container/searxng>

## Pre-promotion gates

- Exact tag, commit, multi-arch manifest and linux/amd64 digest were resolved
  independently; all three deployment references now use one tag-plus-digest
  string and a regression test enforces equality.
- Trivy with `vuln`, HIGH/CRITICAL, and `--ignore-unfixed` reported zero fixed
  HIGH or CRITICAL findings for the candidate image.
- Isolated VM232 canary on `127.0.0.1:28089` used the production settings. On
  three queries, old and new images each returned HTTP 200 and 20 JSON results;
  the Thin Signals `SearxConnector` parsed five bounded hits from the candidate.
- The current GPT Researcher stable release remains v3.7.0, so it was not
  bundled into this module upgrade.
- Home-PVE snapshot `pre-searxng-20261012` was created immediately before the
  production checkout/promotion. `local-zfs` had about 668 GB available.

## Production evidence

- VM232 updated through SourceCraft to `16d86974834f`; no files were
  copied between checkouts.
- Compose recreated only `thin-signals-research-searxng-1`. GPT Researcher's
  container ID stayed
  `a25cafadbd8e572bbb58da0b7a19c716d9b389aa254dcaa74dc1400e7daae23e`.
- Runtime image ID exactly matches the audited amd64 digest
  `sha256:00ad29bb7d72d896ac3b3ff8b252d9ad9939da3e014828934363c61dba9b7e09`.
- Direct JSON returned 20 results; the product connector returned five; sampled
  results reported engine `google cse`.
- SearXNG stayed on `127.0.0.1:28088`; GPT Researcher stayed on
  `127.0.0.1:28000`. API `:8095`, UI `:8501` and the public domain all returned
  HTTP 200.
- A controlled SearXNG-only restart returned to healthy and JSON HTTP 200;
  GPT Researcher remained healthy and unchanged.
- A disposable PostgreSQL database was migrated, all 234 tests passed, ruff
  passed, LivingSet links passed, and production Compose validation passed.
  The disposable database was dropped; production data was not modified.

## Observed non-regressions and limits

Both exact old and new images emit the same startup warnings for Ahmia/Torch,
bind-mount ownership, missing limiter configuration and direct requests without
forwarded-IP headers. Both become healthy and serve the required JSON contract.
These warnings are therefore not an upgrade regression, but they remain a
separate hardening/observability item. The sampled SearXNG result set used only
one engine; direct product connectors still run independently, so engine
diversity is not claimed.

## Rollback

The old image remains present on VM232. A failed runtime gate can be rolled back
by restoring the previous tag-plus-digest and recreating only SearXNG. The
stronger rollback is Home-PVE snapshot `pre-searxng-20261012`. PostgreSQL and
the `/srv/thin-signals-research` data were untouched by the upgrade.
