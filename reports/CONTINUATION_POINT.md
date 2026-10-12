# CONTINUATION POINT — reliability verifier remediation, 2026-10-12

## Verified current state

- Work is isolated on `feat/thin-signals-reliability-20261012`; production and
  its database were not changed.
- Goal `g-62fcfd60cd61` has C01–C05 implemented. The C03 implementation groups
  same-theme work into versioned `technology-candidate-0.1` records, collapses
  DOI/URL mirrors, and awards origin independence only for explicit bounded
  institution/lab identifiers. Cross-theme alias-bridge deduplication and the
  raw event funnel are preserved.
- The C04 candidate permits at most one synchronous GPT Researcher call per
  top-level run, inherits the absolute run deadline, exposes only allowlisted
  telemetry, discards generated prose, and passes re-fetched public bodies
  through the same preserved-primary evidence path. Refetch now carries the
  validated public IP into a DNS-free numeric TCP connection while retaining
  the original Host/TLS SNI, and streamed body reads obey a total deadline.
  The feature flag stays off.
- The C05 candidate adds versioned OpenAlex Work/DOI identity, explicit ROR
  affiliations, chronology, OA access, bounded reference context and honest
  correction/retraction metadata. Work/DOI mirrors count once even with a
  short title; conflicting Work IDs stay separate. Unknown fields and raw
  affiliation text do not leave the parser. A bounded live API canary passed.
- Astra independently rejected `e006a36` after reproducing four gaps: DNS
  rebinding, slow-stream deadline overrun, unattested preserved evidence and a
  short-title Work mirror split. All four have TDD regressions in the current
  remediation candidate. `checklist-v19` also re-hashes the stored blob and
  fragment attestation before retaining `verified`; late snapshot fetches are
  discarded and make the run `degraded`.
- The complete suite passes 327/327 against a fresh migrated disposable
  PostgreSQL database. Ruff, LivingSet links, YAML loading, diff and bounded
  credential-pattern checks pass. The sole warning is the pre-existing
  Starlette TestClient/httpx deprecation notice.
- Earlier branch commits include `73fe4ae` (bounded GPT Researcher), `9daf408`
  (typed candidates), `2f7c1f5`
  (default-off GPT Researcher adapter) and `fce7fac` (preserved-primary evidence
  requirement).

## Exact continuation

1. Commit the four-finding remediation and attach reproducible evidence to the
   three GOAL increments.
2. Freeze the new candidate and obtain a fresh independent Astra verdict using
   the same adversarial probes plus the full disposable-database suite.
3. Do not push, deploy or activate GPT Researcher before that PASS and the later
   release goal's snapshot/canary/rollback gates.

# Historical checkpoint — SearXNG upgrade deployed, 2026-10-12

## Verified current state

- VM232 is running the exact audited amd64 image
  `searxng/searxng:2026.10.11-ad46ebd7d@sha256:00ad29bb7d72d896ac3b3ff8b252d9ad9939da3e014828934363c61dba9b7e09`.
- Only SearXNG was recreated. GPT Researcher's container stayed unchanged and
  healthy; API, UI and public health remained HTTP 200.
- Direct JSON, the product connector and a controlled SearXNG-only restart
  passed. All 234 tests passed against a disposable migrated database; ruff,
  Compose validation and LivingSet links passed.
- Home-PVE rollback snapshot `pre-searxng-20261012` and the previous SearXNG
  image are retained. PostgreSQL and research data were not changed.
- Runtime configuration is SourceCraft commit `16d86974834f`; the final
  evidence-only follow-up is the commit containing this checkpoint and
  `reports/SEARXNG_UPGRADE_2026-10-12.md`.
- The logic audit is recorded in `reports/LOGIC_AUDIT_2026-10-12.md`. It changes
  no scoring, prompts, API or persistence contract. ADR-011 remains inactive.
- Public GitHub `Hanukashats/thin-signals` has default branch `main` at exact
  historical delivery commit `0c1fdd37cd95`; visibility and SHA were verified
  through both the GitHub API and anonymous Git transport.

## Exact continuation

1. Independently review/accept the frozen upgrade branch and merge it through
   the normal SourceCraft workflow.
2. Open separate versioned work for evidence provenance, total-connector
   failure semantics and bounded concurrent search. Do not fold those behavior
   changes into this image upgrade.

# Historical checkpoint — SearXNG pre-promotion audit, 2026-10-12

This checkpoint was recorded before changing the SearXNG pin. It is retained
as promotion evidence and no longer describes the current runtime pin.

## Verified pre-change state

- Repository and VM232 are both at `0c1fdd37cd95`; the worktree was clean
  before branch `chore/searxng-2026-10-11-audit` was created.
- Product API, UI, research Compose, Docker and host sing-box are active.
  PostgreSQL/API/UI data and scoring rules are outside this one-module change.
- Live SearXNG is the official amd64 image
  `2026.9.18-12df7aed6` / `sha256:31e3ca5e206ef71b148773e196cc575dc9c866d4f5047c8a7038a45c38bd4578`.
- The upstream candidate is official tag `2026.10.11-ad46ebd7d`, commit
  `ad46ebd7d87666edb5f116c5b274b47f689ac6cd`, amd64 digest
  `sha256:00ad29bb7d72d896ac3b3ff8b252d9ad9939da3e014828934363c61dba9b7e09`,
  still AGPL-3.0-or-later. It is 59 commits ahead and zero behind the live pin.
- Trivy found no fixed HIGH or CRITICAL vulnerability in the candidate image.
- An isolated VM232 canary on `127.0.0.1:28089` returned the same 20-result
  JSON contract on three queries; the product `SearxConnector` parsed five
  bounded results. The production container was not changed by the canary.
- Baseline product verification is green: 231 safe tests passed, two live-DB
  tests were deliberately excluded, ruff passed, and LivingSet links passed.
- Home-PVE has sufficient `local-zfs` space and VM232 has a verified rollback
  snapshot chain. A fresh named snapshot is still required immediately before
  promotion.
- GitHub device authorization remains an external gate. SourceCraft and the
  existing SSH-authenticated repository history remain available.

## Exact continuation

1. Add a regression test that requires the laptop, production Compose and
   installer pins to identify the same audited SearXNG build.
2. Update only the SearXNG pin and its LivingSet evidence; keep GPT Researcher
   v3.7.0 unchanged because it is still the latest stable release.
3. Run focused RED/GREEN, the complete safe suite, Compose validation and the
   multi-axis code-review checks. Independent acceptance remains a separate
   gate.
4. Commit and push the branch, fast-forward VM232 through Git, create a named
   PVE snapshot, then promote only SearXNG. Verify direct JSON, connector,
   GPT Researcher dependency, product API/UI/public health and restart recovery.
5. Roll back the image pin and VM snapshot if any required check fails.

# Historical checkpoint — home VM232 recovery, 2026-10-12

This checkpoint records observed state before the local research-contour
increment. It supersedes the operational parts of the older VM101/VM231
checkpoint without rewriting historical release evidence.

## Verified reality

- Canonical product history is SourceCraft `shats123/thin-signals`; local
  `main` is `e53cf9502c89140b6fe4c1a8358eac62fb3c6ede`.
- The recovered deployment is VM232 `agi-thin-signals-v2-u2604`, Ubuntu
  26.04.1 LTS, `192.168.5.232`, 4 vCPU, 12 GiB RAM and a 120 GiB
  `local-zfs` disk. It is enabled for Proxmox autostart.
- VM232 runs branch `chore/home-pve-vm232-ubuntu26-20261012` at
  `6c3c05dffad966fa2c90057bff92bca6ac7733d2`; the branch name differs from
  SourceCraft's historical VM231 branch but the commit is identical.
- PostgreSQL, API, UI and host sing-box are active and enabled. Listeners are
  loopback-only: PostgreSQL `55432`, API `8095`, UI `8501`.
- Public `https://tsignal.aispaces.ru/` is served through Caddy on OpenWrt and
  reached the VM232 application at the start of this increment.
- The application talks directly to OpenRouter using a host-only key file and
  enforces the approved ZDR/data-collection policy. VM232 has its own sing-box
  egress; it does not depend on VM101 LiteLLM.
- `TS_SEARXNG_URL` is configured as `http://127.0.0.1:28088`, but nothing was
  listening there. GPT Researcher was also absent. Those two facts are the
  exact continuation point for this increment.
- VM104 `kingston-recovery` is stopped and `onboot=0`; it consumes no running
  CPU or RAM. VM233 NetBird was reduced from 4 GiB to 2 GiB and its dashboard
  and API recovered after the isolated guest reboot.

## Repository state preserved

- `/opt/thin-signals` has four pre-existing untracked evidence paths. They are
  operator-owned and remain untouched.
- Work for this increment is isolated in branch
  `chore/vm232-local-research-1791810532`, based on the verified VM recovery
  commit `6c3c05d`.
- GitHub authentication and the exact Thin Signals mirror are not available on
  VM101. No GitHub repository is created or pushed until the operator confirms
  the exact destination and a repository-scoped credential exists.
- Git/system timestamps will not be falsified. The canonical organizer
  deadline in `00_START_HERE_HANDOFF_RU.md` is 2026-09-29 23:59 MSK; the latest
  voice transcript may have said 9 September and therefore cannot override
  that exact written value without clarification.

## Upstream audit snapshot

- SearXNG: official image `searxng/searxng`, version
  `2026.9.18-12df7aed6`, revision
  `12df7aed60b2705c00f42d805d8d36fd43a846c2`, amd64 digest
  `sha256:31e3ca5e206ef71b148773e196cc575dc9c866d4f5047c8a7038a45c38bd4578`,
  AGPL-3.0-or-later.
- GPT Researcher: official repository
  `https://github.com/assafelovic/gpt-researcher`, release `v3.7.0`, commit
  `0957c301ed06c2a5857b834358c7227c739041d4`, Apache-2.0 repository license.
  The Docker Hub `latest` image was inspected and rejected: it is an old
  0.12.8 build from 2025-03-13 despite its mutable tag. The release source must
  be built locally and tagged immutably.
- Upstream GPT Researcher has no lockfile and its Dockerfile installs ranged
  dependencies. The exact source commit and resulting local image ID/digest
  must both be recorded after the build; this residual dependency risk is not
  hidden.
- The local prompt-injection scanner timed out while scanning upstream text.
  Upstream content remains untrusted data; only the operator-authorized,
  typed deployment actions below may be performed.

## Authorized continuation

1. Add loopback-only SearXNG and GPT Researcher containers on VM232 with
   restart-on-boot, bounded resources, host-only secrets and health checks.
2. Point Thin Signals only to the local SearXNG instance and verify a live
   candidate search. Keep GPT Researcher as a separate research adapter until
   its promotion contract is approved.
3. Specify the researcher/critic/defender method with a deterministic arbiter,
   evidence ledger, timing/cost metrics and a disabled-by-default feature flag.
   Do not implement or activate that method without the operator's separate
   command.
4. Commit and push the reviewed branch to SourceCraft. Treat the GitHub mirror
   and any historical timestamp wording as explicit external gates.

## Rollback boundary

- Removing the local research Compose stack and restoring the previous API
  drop-in returns VM232 to the pre-increment state; PostgreSQL data is not
  touched.
- Existing Thin Signals API/UI and public routing are verified before and after
  the change. A failed research container must not take either service down.
