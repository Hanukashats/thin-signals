# Independent release verification — 4074e51

Date: 2026-10-14 UTC. Verifier: `astra-verifier`.
Frozen candidate: `4074e51afaf6ee85374e3e48a13778c812cd251f`.
Branch: `feat/thin-signals-reliability-20261012`.
Release GOAL: `g-277a6c4d68e2`, criterion C05.

## Verdict

**C05 FAIL.** One reproducible P1 provenance defect blocks independent release
acceptance despite passing repository tests and healthy production services.
No P0 or additional P2 finding was established in this bounded audit. The
public-health wording has a P3 evidence clarification below.

The existing rollout is already active. This audit neither disabled it nor
changed product code, settings, remotes, services, production data or snapshots.
Only this report is added to the previously clean worktree. The explicitly
designated disposable test database was used and retained. No live model or
GPT Researcher requests were issued. The release GOAL is not verified PASS.

## Findings, ordered by severity

### P1 — missing organization identity becomes invented DOI independence

`ts/review/integration.py:83` falls back from absent `origin_ids` to
`doi:<document DOI>` and supplies this value as `EvidenceItem.origin_group_id`.
The arbiter credits these values both when validating additive independent
evidence (`ts/review/arbiter.py:141`) and at its final two-origin gate
(`ts/review/arbiter.py:197`). Different documents from one laboratory can
therefore be counted as independent origins when institution metadata is
missing.

This directly contradicts `docs/METHODOLOGY.md:14`: DOI/URL identify work,
while independent groups require explicit organization/laboratory identifiers.
It also defeats ADR-014's requirement for two independent preserved-primary
origins. The issue is in the deployed product evidence adapter, outside the
authored evaluation fixtures' explicit ROR-only assumptions.

An independent in-memory differential used the repository's existing typed
candidate and adaptive gateway fixture, through the real
`CandidateEvidenceProvider` and `run_review`; there was no model, database or
network call:

| Same candidate and DOI records | Adapter origins | Actual verdict |
|---|---|---|
| Three distinct explicit ROR values | Three ROR values | PROMOTE |
| Every source explicitly assigned to one lab | `ror:one-lab` for all | HOLD / unresolved_critical |
| All explicit origin metadata removed | Three different `doi:10.1234/review-N` values | **PROMOTE** |

Every role and the arbiter reported `succeeded` in each probe. Removing known
same-lab identity must not turn HOLD into PROMOTE. The fixture's preserved
fragment assumptions are identical across all three cases; this differential
tests origin attribution, not snapshot acquisition.

Reproduction, run from the frozen checkout:

```python
from ts.review.integration import CandidateEvidenceProvider
from ts.review.runner import RoleBudget, ReviewModels, run_review
from ts.tests.test_review_integration import _card, AdaptiveGateway

budget = RoleBudget(5, 500, 0.02, 3)
for mode in ("same", "missing"):
    card = _card()
    for source in card["sources"]:
        if mode == "same":
            source["origin_ids"] = ["ror:one-lab"]
        else:
            source.pop("origin_ids")
    provider = CandidateEvidenceProvider(card)
    result = run_review(
        run_id="origin-independent-audit",
        candidate=card,
        gateway=AdaptiveGateway(),
        evidence_provider=provider,
        budget=budget,
        models=ReviewModels("model-primary", "model-judge"),
    )
    print(mode, result.decision.verdict, result.decision.reason_codes)
```

Required remedy: preserve DOI as document identity only; unknown organization
identity must remain unknown at the review origin boundary. Add the above
differential as a regression, retain valid explicit-origin promotion and
same-origin HOLD, then freeze a new SHA for independent verification.

### P3 — public UI HTTP 200 does not establish public API health

The release receipt says the public URL and its API health route return 200.
Direct probes of `/api/health` and `/health` on the public hostname returned
the Streamlit HTML shell, not the API health JSON. These 200 responses must not
be counted as API-health evidence. The actual private API was independently
healthy: `http://127.0.0.1:8095/health` returned `{"ok":true}` and `/ready`
returned `{"ok":true,"database":"ready"}` on VM232. No public API exposure
is requested or implied by this clarification.

## Verified release evidence

### Git and publication

- Local HEAD and VM232 `/opt/thin-signals` both equal the exact frozen SHA.
  Both worktrees were clean before this report.
- Read-only `git ls-remote` independently returned the same candidate SHA for
  both named feature branches: SourceCraft and public GitHub.
- GitHub historical `main` remains
  `0c1fdd37cd95da5013ef27237b3657637601cf32`.
- SourceCraft `main` is its distinct historical delivery snapshot
  `f56f6ff57e4f4b83ae7c2e9dbff36cb238e0ade5`, dated
  `2026-09-29T22:40:00+03:00`; it was not moved to this release.
- Candidate author and committer times are both `2026-10-14T00:26:35Z`.
  Intermediate release commits retain 2026-10-13 execution dates. The older
  delivery commit is an ancestor. These direct observations corroborate the
  no-rewrite account; remote server reflogs were not available for a forensic
  proof that no force push ever occurred.
- SourceCraft authentication used the existing askpass consumer without
  inspecting or printing its credential material.

### Runtime, boundaries and resources

At approximately 00:31 UTC on 2026-10-14:

- `thin-signals-api`, `thin-signals-ui`, `thin-signals-research`, `docker`,
  `agi-sing-box` and `netbird` are all active and enabled.
- PostgreSQL, SearXNG and GPT Researcher containers are healthy and use
  `unless-stopped`. No failed systemd units were present.
- API `8095`, UI `8501`, PostgreSQL `55432`, SearXNG `28088` and GPT Researcher
  `28000` are bound to loopback. Application ingress is the private
  `192.168.5.232:18443` socket proxy. The separate wildcard sing-box listener
  was identified as sing-box, not an application service.
- API and UI have `DynamicUser`, `NoNewPrivileges`, `PrivateTmp`,
  `ProtectHome` and `ProtectSystem=strict` enabled.
- SearXNG runs exact digest
  `sha256:70f100d04af1ac841d59ffc1b6354e9e264c161ae47d5251be4e598013386065`;
  image labels identify `2026.10.13-22c64b8d3` and upstream revision
  `22c64b8d394b680c7ea96be25f36dad14126420a`.
- GPT Researcher image is
  `sha256:ef799f7f83bed75ec04a445cdb98c8353bea14a659f0bd69892ee459e3b59520`;
  labels identify v3.7.0 and upstream commit
  `0957c301ed06c2a5857b834358c7227c739041d4`.
- Both research containers have the documented capability restrictions,
  `no-new-privileges`, CPU, memory and PID limits, and bounded JSON logs.
- VM232 has 4 CPUs, 12 GiB assigned RAM, a 120 GiB disk, `onboot=1` and
  startup order 30. Direct observation found about 10 GiB memory available,
  103 GiB disk available, load averages `0.06/0.09/0.03`, and 8 hours uptime.
- Container memory samples: SearXNG 142 MiB, GPT Researcher 335 MiB,
  PostgreSQL 77 MiB. This is a bounded idle-health observation, not a load
  capacity or throughput benchmark.
- Public `https://tsignal.aispaces.ru/` returned HTTP 200 with successful TLS
  verification, HSTS, nosniff and SAMEORIGIN headers via Caddy. The HTTP probe
  used the operator host's configured network path; it is not an independent
  external-location availability measurement.

### Saved production canaries and safe ledger

Read-only SQL confirmed these saved runs without rerunning research:

| Field | Narrow `91e9ffd0d5ffd01e` | Wide `c1ffe5d3282324d4` |
|---|---|---|
| Rules | rules-0.1 | rules-0.1 |
| Run state | degraded | degraded |
| Source records | 49 (47 unique in funnel) | 733 unique |
| Admitted / potential / near miss | 2 / 5 / 8 | 9 / 0 / 0 |
| Themes | Not a wide run | 13 |
| Theme failures / degraded | 0 / 0 | 0 / 13 |
| Connector failures | 3 | 6 |
| Deadline exhausted | false | false |
| Review verdict | HOLD / invalid_role_output | HOLD / insufficient_origin_diversity |
| Role states | Researcher and defender invalid; critic, control and arbiter succeeded | All five succeeded |
| Preserved source attestations checked | 10 / 10 valid | 180 / 180 valid |

The nine admitted wide themes match the receipt: carbon, heat, CMOS,
bioprocess, link, nuclear, motor, quantum and molecular. Fifteen narrow
surfaced rows are three distinct queues, not fifteen promoted technologies.
Neither saved canary demonstrates an unsafe promotion; the P1 counterexample
is an additional deterministic probe.

Each run has exactly five persisted review events. Four model-role budgets
are identical: 45 seconds, 1,200 output tokens, USD 0.03 and 12 evidence items.
Recorded policies are ZDR true and data_collection deny. A recursive key check
of the selected persisted events found no statement, promotion_hypothesis,
uncertainties, messages, system_prompt, chain_of_thought, quote or raw
affiliation fields. Snapshot validation read only the referenced stored bodies
and emitted counts, not source contents or credentials.

### Rollback evidence

- Home-PVE directly lists `pre-reliability-17c36e9-20261013` and
  `pre-searxng-20261013` snapshots.
- The exact database archive exists, is 1,936,171 bytes and mode 0600.
  `pg_restore --list` accepts it; SHA-256 equals
  `09ccdf72cd19bcfc00a0118e59b1e66796af7cde7d3c6db140ffa1331b36620b`.
- Installed review activation drop-in SHA-256 equals
  `cb33494e38fc534e82054aa5075990ec64afaab5a4c7d48d838674ca30030b87`.
- API journal entries show two stop/start sequences at 23:50:36–23:50:39 UTC
  on October 13, each followed by `/ready` HTTP 200. This corroborates the
  operator's recorded disable/restore rehearsal; the journal alone does not
  reconstruct each historical environment value. No restore or restart was
  performed during this audit.

## Reproduced repository gates

| Gate | Independent result |
|---|---|
| Full suite on specified disposable PostgreSQL | **464 passed**, 1 existing Starlette warning, 16.42 s |
| Database identity/schema | thin_signals_test_codex_20261013_r2 / e2c7f6a9b104 |
| Ruff: ts ui scripts docs/presentation | All checks passed |
| LivingSet | OK requirements=52 waves=19 forks=13 |
| git diff --check, worktree and 17c36e9..4074e51 | PASS |
| Production research Compose config --quiet | PASS |
| Quick-deploy Compose config --quiet | PASS with existing host env-file directory |
| Review evaluation recomputation | Committed JSON equality and rendered Markdown equality |
| Additional origin differential | **FAIL**, as above |

The disposable test database existed before inspection; it was neither
created nor dropped by this audit. The successful suite command was:

```bash
TS_DISABLE_DOTENV=1 \
TS_DATABASE_URL=postgresql+psycopg://ts@127.0.0.1:55432/thin_signals_test_codex_20261013_r2 \
TS_PG_PASSWORD_FILE=/opt/thin-signals/.secrets/pg_password \
TS_OPENROUTER_KEY_FILE='' TS_GPT_RESEARCHER_ENABLED=false \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

An initial verifier invocation incorrectly used `/nonexistent` as a disabled
key path; that path exists but is unreadable on this host and caused 23
configuration failures. Correcting the verifier environment to the supported
empty path yielded the full passing suite. This was not a product-code fix.

Quick-deploy Compose parsing used `TS_SECRETS_DIR=/etc/thin-signals-research`
to consume the existing SearXNG env file without creating secret files. This
checks Compose syntax only, not quick-deploy secret readiness or deployment.
The production research Compose uses its actual host environment file.

In-memory `evaluate_review_dataset(load_review_dataset(...))` exactly
reproduced the committed evaluation and rendered report. Result digest:
`66de648ca54cfd9b33e405a720f7dec00051d409f0c18f42f45a8cd19cc1e0eb`.
All 16 authored cases retain proposed P/R/exact/stability 1.0 and zero unsafe
acceptances. These are deterministic fixture results, not independent
scientific generalization or live-model accuracy. The uncovered DOI-origin
counterexample shows why those aggregate numbers are insufficient for C05.

## Disposition

**VERIFIED:** exact checkout/mirror/deployment equality, current private
service health, reported canary counts and HOLD states, selected snapshot and
ledger provenance, retained rollback assets, passing static/full-test gates.

**FAIL:** release C05 due to the reproduced P1 origin-independence bypass.
**NEXT TRIGGER:** implement and test the explicit-origin-only correction,
freeze a new candidate, and request fresh independent verification.

No `goalctl verify ... pass` is permitted for this candidate.
