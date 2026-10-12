# Implementation plan: VM232 local research and adversarial review

## Scope and assumptions

The authenticated operator approved the local research infrastructure on VM232
and explicitly kept NetBird separate from OpenWrt. The adversarial methodology
is a separate operator gate: this increment specifies it but does not implement
or activate it.

No Git or system timestamp is backdated. SourceCraft is the only currently
authenticated repository destination; the exact GitHub mirror remains open.

## Capability map

| Module id | Responsibility | Depends on | State |
|---|---|---|---|
| `local-search` | Private SearXNG used by Thin Signals and GPT Researcher | VM232 Docker, sing-box | approved |
| `deep-research` | Private GPT Researcher API using local SearXNG | `local-search`, OpenRouter secret | approved |
| `adversarial-review` | Researcher/critic/defender ledger and arbiter | existing harness, PostgreSQL | proposed; operator gate |
| `release-evidence` | Tests, timings, rollback receipt and repository parity | preceding modules | approved, GitHub blocked |

Build order: `local-search` → `deep-research` → `release-evidence`.
`adversarial-review` starts only after a new operator command.

## Architecture decisions

- Both new services bind only to VM232 loopback. There is no new Caddy route,
  LAN listener or Internet-facing endpoint.
- SearXNG is pinned to an official immutable image digest. GPT Researcher is
  built from official release `v3.7.0` because Docker Hub `latest` is an old
  0.12.8 image.
- GPT Researcher receives the OpenRouter key through a Docker secret and sends
  the approved ZDR/data-collection request policy. It uses keyword context
  filtering, so no backend embedding service is required.
- GPT Researcher output is advisory. Only directly fetched source fragments
  may enter the Thin Signals evidence ledger.
- Docker restart policy plus an enabled systemd Compose unit provide boot
  recovery. The existing API/UI units stay independent.

## Task list

### Phase 1: Local search

- Add pinned Compose, SearXNG settings, boot unit and installer.
- Validate Compose without exposing secrets.
- Deploy on VM232 and prove JSON search through `127.0.0.1:28088`.
- Point the API service at the local endpoint and verify public health.

### Checkpoint: search

- Containers healthy; only loopback ports are open.
- API/UI/public endpoint remain healthy if GPT Researcher is stopped.

### Phase 2: Deep research

- Build official GPT Researcher `v3.7.0` from exact commit.
- Run a bounded research canary through local SearXNG and direct OpenRouter.
- Record source count, duration, model/provider policy and image identity.

### Checkpoint: runtime

- Reboot-safe service state is proven by controlled container/service restart.
- No secret appears in Git, Compose rendering, logs or the operator report.

### Phase 3: Method proposal

- Define role inputs/outputs, evidence-only rebuttal and deterministic verdicts.
- Define append-only timing/cost/evidence metrics and evaluation gates.
- Leave the feature flag disabled and make implementation depend on a new
  operator command.

### Phase 4: Release evidence

- Run repository tests, lint and living-link checks.
- Review the diff, commit atomically and push SourceCraft branch.
- Mirror only after the exact GitHub URL and scoped authentication are given.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| GPT Researcher dependencies are range-pinned | rebuild drift | record source SHA and built image ID; retain rollback image |
| Web content prompt injection | false or unsafe synthesis | advisory output only; direct evidence validation; no tools/actions |
| OpenRouter privacy policy drift | data exposure | force ZDR/no-collection request body; never route through an unknown proxy |
| Search engines throttle SearXNG | incomplete coverage | connector failure ledger; multiple native sources remain active |
| Added containers affect product | outage | loopback isolation, resource limits, independent units and rollback |

## Open operator gates

- Exact GitHub repository URL and repository-scoped credential.
- Whether “9 September” in the voice transcript means 2026-09-09 or the
  canonical organizer deadline 2026-09-29. Neither changes real commit times.
- Separate command to implement and activate `adversarial-review`.

