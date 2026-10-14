# Thin Signals 7.8 reliability release — 2026-10-14

Status: **FINAL PASS — production, mirrors and independent verification complete**

This receipt covers the reliability branch
`feat/thin-signals-reliability-20261012`. Git author and committer timestamps
are the real execution times. `2026-09-29 23:40 MSK` is retained only as
historical delivery metadata; no commit history was rewritten.

## Release boundary

- Production remains on `rules-0.1`; weights, thresholds and P01–P18 were not
  relaxed. `rules-0.2` remains an evaluated, versioned candidate rather than a
  silent production replacement.
- The local research contour is SearXNG
  `2026.10.13-22c64b8d3` at linux/amd64 digest
  `sha256:70f100d04af1ac841d59ffc1b6354e9e264c161ae47d5251be4e598013386065`
  plus GPT Researcher `v3.7.0` at commit
  `0957c301ed06c2a5857b834358c7227c739041d4`.
- On 2026-10-13 the official SearXNG `latest` amd64 manifest resolved to the
  same pinned digest. The official GPT Researcher latest stable release was
  still `v3.7.0`.
- OpenAlex provides typed scholarly metadata and open-access locations. Every
  promoted citation is still refetched, typed and snapshot-attested by Thin
  Signals; generated research prose is advisory only.
- The researcher, critic, defender and control critic have closed schemas,
  equal budgets and exact citation bindings. A deterministic arbiter is the
  only component allowed to issue the final verdict. Invalid or unavailable
  model output becomes `HOLD`.

## Rollback and deployment

- Home-PVE snapshot: `pre-reliability-17c36e9-20261013`.
- PostgreSQL custom archive:
  `/var/backups/thin-signals/pre-reliability-17c36e9-20261013.dump`, validated
  with `pg_restore --list`, SHA-256
  `09ccdf72cd19bcfc00a0118e59b1e66796af7cde7d3c6db140ffa1331b36620b`.
- SearXNG pre-update snapshot: `pre-searxng-20261013`.
- The candidate was first deployed with adversarial review disabled. API, UI,
  PostgreSQL, SearXNG and GPT Researcher passed readiness before activation.
- Activation is one credential-free systemd drop-in. Moving that exact file
  aside, reloading systemd and restarting the API disabled the feature while
  readiness stayed healthy; restoring the identical SHA-256
  `cb33494e38fc534e82054aa5075990ec64afaab5a4c7d48d838674ca30030b87`
  re-enabled it. No database restore was required.
- A prior controlled VM reboot restored PostgreSQL, API, UI, Docker, host
  `agi-sing-box`, SearXNG and GPT Researcher automatically. Home-PVE retains
  `onboot=1`, startup order 30 for VM232.

## Verification

- Frozen `4074e51` disposable PostgreSQL suite: **464 passed**, one upstream
  Starlette deprecation warning, zero test failures.
- The first independent frozen-SHA audit rejected `4074e51` because missing
  organization IDs incorrectly fell back to DOI document identities. The
  fallback is removed and a regression now proves DOI-only evidence remains
  unknown and `HOLD`; the remediated suite is **465 passed**. Independent
  re-verification of `96550ff` found no scoped P0/P1/P2 issue and accepted C05.
- Ruff: PASS for maintained runtime/test/operations/presentation paths (`ts`,
  `ui`, `scripts`, `docs/presentation`). Frozen lineage and donor copies are
  preserved byte-for-byte and are not reformatted as current code.
- LivingSet links: `OK requirements=52 waves=19 forks=13`.
- `git diff --check`: PASS.
- Production research Compose and secret-free quick-deploy Compose both pass
  `docker compose config --quiet` using host-only environment files.
- Frozen review replay and holdout: precision 1.0, recall 1.0, exact verdict
  1.0, stability 1.0, zero false/evidence-less/unresolved-critical promotions.
  Detailed artifacts are under `reports/eval/review-2026-10-13/`.
- The application image pre-promotion scan reported zero fixable HIGH or
  CRITICAL runtime findings. Research containers keep capability, PID, CPU,
  memory and bounded-log restrictions.
- SourceCraft, GitHub and VM232 resolved to the same reviewed code SHA
  `96550ff131ad9852d85ae2470e79799d86d6e0b5`, with real Git timestamps and
  preserved ancestry. GOAL `g-277a6c4d68e2` is independently `VERIFIED`, 5/5
  PASS. Full evidence is in
  `reports/ASTRA_RELEASE_VERIFICATION_96550FF_2026-10-14.md`.
- Within the product's GOAL cards (`project=thin-signals` plus four legacy
  untagged goals whose objective begins with `Thin Signals`), there is no open
  card. Seven project-tagged cards are `VERIFIED` and four historical or
  superseded cards are `STOPPED`; among the four untagged cards, three are
  `VERIFIED` and legacy HANDOFF `g-2a54ff75ca41` is `STOPPED` as superseded
  rather than being falsely certified against the replacement architecture.
  Total: ten `VERIFIED`, five `STOPPED`, zero open. The separately scoped
  `netbird-mesh-v2` GOAL remains in progress and is not a release dependency.

## Production canaries

### Narrow mechanism query

Run `91e9ffd0d5ffd01e`, query `anode-free sodium metal pouch cell`:

- 49 sources;
- 2 admitted + 5 potential + 8 near misses = **15 surfaced candidates**;
- a malformed provider response was rejected and the deterministic result was
  `HOLD`; no candidate was promoted through the failed role.

A bounded structural replay against the same real candidate subsequently ran
researcher, critic, defender and control critic successfully. This distinguishes
provider variability from a broken role contract while preserving fail-closed
behavior.

The preceding repeat `3a44750c6fc6d25e` independently retrieved the same 49
sources and the same 2 admitted + 5 potential + 8 near-miss split. Its provider
failures also produced `HOLD`; the repeated search did not pad the result.

### Wide mission query

Run `c1ffe5d3282324d4`, Russian 13-theme mission:

- 733 deduplicated source records;
- 13/13 themes executed, zero theme failures and no exhausted deadline;
- **9 evidence-gated technology candidates** admitted across carbon capture,
  heat pumps, CMOS, bioprocessing, satellite links, nuclear, motors, quantum
  processors and molecular design;
- researcher, critic, defender, control critic and arbiter all succeeded;
- verdict `HOLD`, reason `insufficient_origin_diversity`.

This is an honest nine rather than a padded ten: the release does not lower
scientific gates to fill a quota. Together with the separate potential and
near-miss queues, the narrow canary exposes 15 reviewable candidates.

### Additional wide retrieval query

Run `1ac434110b0270a7`, English cross-industry discovery query:

- 694 source records and all 13 planned themes executed;
- **8 evidence-gated candidates** admitted, with no deadline-skipped theme;
- the model review failed closed as `HOLD` on invalid role output.

This second broad run is retrieval/yield evidence, not promotion evidence. It
was saved before the final origin correction; the correction does not change
retrieval or scoring and was separately verified by the deterministic origin
differential and the 465-test suite.

## Runtime state

- VM232: Ubuntu 26.04.1 LTS, 4 vCPU, 12 GiB RAM, 120 GB disk; about 104 GB free
  during release verification.
- PostgreSQL, API, UI, research unit, Docker, NetBird and `agi-sing-box` are
  active and enabled. SearXNG and GPT Researcher containers are healthy.
- Host and research egress observed `144.124.252.222` through the VM-local
  sing-box path.
- `https://tsignal.aispaces.ru` returns the Streamlit UI over HTTPS with HTTP
  200. The API is intentionally private; its loopback `/health` and `/ready`
  routes return healthy JSON. Public `/health`-shaped paths are UI fallbacks
  and are not counted as API-health evidence.
- The only application ingress on VM232 is the private listener
  `192.168.5.232:18443`; TLS remains on Caddy/OpenWrt VM105.

## Remaining non-release backlog

- Provider structured output is not perfectly deterministic. The safety
  behavior is deliberate `HOLD`; future work may add a dedicated review model
  without weakening citation checks.
- All 13 themes returned useful data but their child runs were degraded by
  bounded connector-level failures. No theme failed completely.
- Historical run step-ledger backfill and production promotion of `rules-0.2`
  are separate changes and are not hidden in this release.
- NetBird peer enrollment and recreated access policies are a separate network
  project, not part of the Thin Signals release gate.
